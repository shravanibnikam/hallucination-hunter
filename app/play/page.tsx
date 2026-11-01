import { connection } from "next/server";
import { PlayGame } from "@/components/play-game";
import { studyOpen } from "@/lib/game-service";
export default async function PlayPage() {
  // Read STUDY_STATUS per request, not at build time.
  await connection();
  return <PlayGame studyOpen={studyOpen()} />;
}
