export const SITE_NAME = "MatchPoint";
export const SITE_DESCRIPTION =
  "Prédiction de matchs de tennis ATP : un comparateur de joueurs calculé dans le navigateur, un modèle LightGBM évalué honnêtement face à une baseline Elo, et des finales mythiques rejouées point par point.";
export const REPOSITORY_URL = "https://github.com/ligsow6/MatchPointAI";

export const NAVIGATION = [
  { href: "/", label: "Accueil" },
  { href: "/comparateur", label: "Comparateur" },
  { href: "/performance", label: "Performance" },
  { href: "/rejouer", label: "Rejouer un match" },
  { href: "/methodologie", label: "Méthodologie" },
] as const;
