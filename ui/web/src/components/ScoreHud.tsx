import { DevelopmentCard } from "../state/types";

type Props = {
  activeDevelopments: DevelopmentCard[];
};

export function ScoreHud({ activeDevelopments }: Props) {
  const positives = activeDevelopments.filter((dev) => dev.valence === "positive");
  const negatives = activeDevelopments.filter((dev) => dev.valence === "negative");
  const positiveScore = positives.reduce((sum, dev) => sum + dev.severity, 0);
  const negativeScore = negatives.reduce((sum, dev) => sum + dev.severity, 0);
  const net = positiveScore - negativeScore;

  return (
    <div style={{ background: "#1e293b", padding: 12, borderRadius: 8 }}>
      <strong style={{ color: "#f8fafc" }}>Score</strong>
      <div style={{ color: "#e2e8f0" }}>Active positives: {positiveScore}</div>
      <div style={{ color: "#e2e8f0" }}>Active negatives: {negativeScore}</div>
      <div style={{ color: "#e2e8f0" }}>Net score: {net}</div>
    </div>
  );
}
