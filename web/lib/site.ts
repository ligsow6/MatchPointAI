export const SITE_NAME = "MatchPoint";
export const SITE_DESCRIPTION =
  "Prédiction de matchs de tennis ATP : un modèle LightGBM évalué honnêtement face à une baseline Elo, et des finales mythiques rejouées point par point.";
export const REPOSITORY_URL = "https://github.com/ligsow6/MatchPointAI";

export const NAVIGATION = [
  { href: "/", label: "Accueil", extra: "" },
  { href: "/performance", label: "Performance", extra: "" },
  { href: "/rejouer", label: "Rejouer", extra: " un match" },
  { href: "/methodologie", label: "Méthodologie", extra: "" },
] as const;
