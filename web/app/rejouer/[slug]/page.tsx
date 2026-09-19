import type { Metadata } from "next";
import { socialMetadata } from "@/lib/site";
import { ReplayView } from "@/components/replay/ReplayView";
import { loadReplayIndex } from "@/lib/data";

type Params = { slug: string };

export const dynamicParams = false;

export function generateStaticParams(): Params[] {
  return loadReplayIndex().map((replay) => ({ slug: replay.slug }));
}

export async function generateMetadata({ params }: { params: Promise<Params> }): Promise<Metadata> {
  const { slug } = await params;
  const replay = loadReplayIndex().find((item) => item.slug === slug);
  const title = replay ? `${replay.title} · Replay` : "Rejouer un match";
  const description = replay
    ? `${replay.players[0]} contre ${replay.players[1]} rejoué point par point : ${replay.score}.`
    : "Finales mythiques rejouées point par point.";
  return {
    title,
    ...socialMetadata({
      title: `${title} · MatchPoint`,
      description,
      path: `/rejouer/${slug}`,
    }),
  };
}

export default async function ReplaySlugPage({ params }: { params: Promise<Params> }) {
  const { slug } = await params;
  return <ReplayView slug={slug} />;
}
