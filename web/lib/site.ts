import type { Metadata } from "next";

export const SITE_NAME = "MatchPoint";
export const SITE_DESCRIPTION =
  "Prédiction de matchs de tennis ATP : un comparateur de joueurs calculé dans le navigateur, un modèle LightGBM évalué honnêtement face à une baseline Elo, et des finales mythiques rejouées point par point.";
export const REPOSITORY_URL = "https://github.com/ligsow6/MatchPointAI";
export const SITE_URL = "https://match-point-ai-five.vercel.app";
export const PREVIEW_IMAGE = {
  url: "/og-image.png",
  width: 1200,
  height: 630,
  alt: "MatchPoint : « Qui gagnerait ? », avec la probabilité de victoire avant la finale de Wimbledon 2019 puis son évolution point par point.",
};

export const NAVIGATION = [
  { href: "/", label: "Accueil" },
  { href: "/comparateur", label: "Comparateur" },
  { href: "/performance", label: "Performance" },
  { href: "/rejouer", label: "Rejouer un match" },
  { href: "/methodologie", label: "Méthodologie" },
] as const;

export function socialMetadata(options: {
  title: string;
  description: string;
  path: string;
}): Metadata {
  return {
    description: options.description,
    alternates: { canonical: options.path },
    openGraph: {
      title: options.title,
      description: options.description,
      url: options.path,
      siteName: SITE_NAME,
      type: "website",
      locale: "fr_FR",
      images: [PREVIEW_IMAGE],
    },
    twitter: {
      card: "summary_large_image",
      title: options.title,
      description: options.description,
      images: [PREVIEW_IMAGE.url],
    },
  };
}
