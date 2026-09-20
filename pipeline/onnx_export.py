from dataclasses import dataclass
from pathlib import Path
from typing import Any

import lightgbm as lgb
import numpy as np
import onnx
import onnxruntime as ort
from onnx import TensorProto, helper
from onnxmltools import convert_lightgbm
from onnxmltools.convert.common.data_types import FloatTensorType

from pipeline.model import TrainedModel

ONNX_OPSET = 15
ML_OPSET = 3
PARITY_TOLERANCE = 1e-6
EQUIVALENCE_TOLERANCE = 1e-9
INPUT_NAME = "features"
OUTPUT_NAME = "probabilities"
TREE_OPERATOR = "TreeEnsembleClassifier"


class OnnxParityError(ValueError):
    pass


@dataclass(frozen=True)
class OnnxReport:
    path: Path
    rows: int
    max_difference: float
    float32_difference: float
    trees: int
    size_bytes: int
    rewritten: bool


def trimmed_booster(model: TrainedModel) -> lgb.Booster:
    return lgb.Booster(model_str=model.booster.model_to_string(num_iteration=model.rounds))


def attribute_values(node: onnx.NodeProto) -> dict[str, Any]:
    return {attribute.name: helper.get_attribute_value(attribute) for attribute in node.attribute}


def exact_tree_values(
    node: onnx.NodeProto, booster: lgb.Booster
) -> tuple[list[float], list[float]]:
    """Retrouve, nœud par nœud, les seuils et valeurs de feuille exacts (double) de LightGBM.

    Chaque arbre ONNX est parcouru en parallèle de l'arbre LightGBM ; la conversion est
    refusée si une variable, un type de nœud ou une valeur arrondie ne correspond pas.
    """
    attributes = attribute_values(node)
    positions = {
        key: index
        for index, key in enumerate(
            zip(attributes["nodes_treeids"], attributes["nodes_nodeids"], strict=True)
        )
    }
    leaf_positions = {
        key: index
        for index, key in enumerate(
            zip(attributes["class_treeids"], attributes["class_nodeids"], strict=True)
        )
    }
    thresholds = [float(value) for value in attributes["nodes_values"]]
    leaves = [float(value) for value in attributes["class_weights"]]
    for tree_id, tree in enumerate(booster.dump_model()["tree_info"]):
        pending: list[tuple[int, dict[str, Any]]] = [(0, tree["tree_structure"])]
        while pending:
            node_id, source = pending.pop()
            position = positions[(tree_id, node_id)]
            mode = attributes["nodes_modes"][position].decode()
            if "leaf_value" in source:
                leaf = leaf_positions[(tree_id, node_id)]
                require_same_float32(source["leaf_value"], leaves[leaf], mode == "LEAF")
                leaves[leaf] = float(source["leaf_value"])
                continue
            same_feature = attributes["nodes_featureids"][position] == source["split_feature"]
            require_same_float32(
                source["threshold"], thresholds[position], mode == "BRANCH_LEQ" and same_feature
            )
            thresholds[position] = float(source["threshold"])
            pending.append((attributes["nodes_truenodeids"][position], source["left_child"]))
            pending.append((attributes["nodes_falsenodeids"][position], source["right_child"]))
    return thresholds, leaves


def require_same_float32(exact: float, rounded: float, structure_matches: bool) -> None:
    with np.errstate(over="ignore"):
        same_value = np.float32(exact) == np.float32(rounded)
    if not (structure_matches and same_value):
        raise OnnxParityError("L'arbre ONNX ne correspond pas à l'arbre LightGBM")


def promote_to_double(model: onnx.ModelProto, booster: lgb.Booster) -> None:
    """Passe les seuils, les feuilles et l'entrée en double précision (ai.onnx.ml v3)."""
    node = next(item for item in model.graph.node if item.op_type == TREE_OPERATOR)
    thresholds, leaves = exact_tree_values(node, booster)
    kept = [item for item in node.attribute if item.name not in ("nodes_values", "class_weights")]
    del node.attribute[:]
    node.attribute.extend(kept)
    node.attribute.append(
        helper.make_attribute(
            "nodes_values_as_tensor",
            helper.make_tensor("nodes_values", TensorProto.DOUBLE, [len(thresholds)], thresholds),
        )
    )
    node.attribute.append(
        helper.make_attribute(
            "class_weights_as_tensor",
            helper.make_tensor("class_weights", TensorProto.DOUBLE, [len(leaves)], leaves),
        )
    )
    for opset in model.opset_import:
        if opset.domain == "ai.onnx.ml":
            opset.version = ML_OPSET
    model.graph.input[0].type.tensor_type.elem_type = TensorProto.DOUBLE
    onnx.checker.check_model(model)


def float_conversion(booster: lgb.Booster) -> onnx.ModelProto:
    model: onnx.ModelProto = convert_lightgbm(
        booster,
        initial_types=[(INPUT_NAME, FloatTensorType([None, booster.num_feature()]))],
        zipmap=False,
        target_opset=ONNX_OPSET,
    )
    return model


def convert(booster: lgb.Booster) -> onnx.ModelProto:
    """Conversion onnxmltools, puis passage en double pour reproduire LightGBM à 1e-6 près."""
    model = float_conversion(booster)
    promote_to_double(model, booster)
    return model


def onnx_probabilities(
    model: onnx.ModelProto, features: np.ndarray, dtype: type[np.floating] = np.float64
) -> np.ndarray:
    options = ort.SessionOptions()
    options.log_severity_level = 3
    session = ort.InferenceSession(
        model.SerializeToString(), options, providers=["CPUExecutionProvider"]
    )
    outputs = session.run([OUTPUT_NAME], {INPUT_NAME: np.asarray(features, dtype=dtype)})
    return np.asarray(outputs[0], dtype=float)[:, 1]


def float32_divergence(booster: lgb.Booster, features: np.ndarray) -> float:
    """Écart maximal de la conversion standard (simple précision), mesuré pour mémoire."""
    expected = np.asarray(booster.predict(features), dtype=float)
    observed = onnx_probabilities(float_conversion(booster), features, np.float32)
    return float(np.max(np.abs(observed - expected)))


def check_parity(model: onnx.ModelProto, booster: lgb.Booster, features: np.ndarray) -> float:
    """Écart maximal entre ONNX Runtime et LightGBM ; au-delà de 1e-6, l'export est refusé."""
    expected = np.asarray(booster.predict(features), dtype=float)
    difference = float(np.max(np.abs(onnx_probabilities(model, features) - expected)))
    if not difference <= PARITY_TOLERANCE:
        raise OnnxParityError(f"Écart ONNX / LightGBM de {difference:.2e} (> {PARITY_TOLERANCE})")
    return difference


def matches_published(model: onnx.ModelProto, path: Path, features: np.ndarray) -> bool:
    """Le modèle déjà publié donne-t-il exactement les mêmes probabilités que le nouveau ?

    L'entraînement LightGBM n'est pas reproductible au bit près : quelques seuils varient
    dans leurs derniers chiffres d'une exécution à l'autre, sans rien changer aux prévisions.
    """
    if not path.exists():
        return False
    published = onnx.load(str(path))
    difference = np.max(
        np.abs(onnx_probabilities(published, features) - onnx_probabilities(model, features))
    )
    return bool(difference <= EQUIVALENCE_TOLERANCE)


def export_onnx(model: TrainedModel, features: np.ndarray, path: Path) -> OnnxReport:
    booster = trimmed_booster(model)
    converted = convert(booster)
    difference = check_parity(converted, booster, features)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = converted.SerializeToString()
    rewritten = not matches_published(converted, path, features)
    if rewritten:
        path.write_bytes(payload)
    return OnnxReport(
        path=path,
        rows=len(features),
        max_difference=difference,
        float32_difference=float32_divergence(booster, features),
        trees=booster.num_trees(),
        size_bytes=path.stat().st_size,
        rewritten=rewritten,
    )
