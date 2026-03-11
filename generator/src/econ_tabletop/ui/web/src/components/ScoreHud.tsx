import { DevelopmentCard } from "../state/types";

type Props = {
  activeDevelopments: DevelopmentCard[];
};

export function ScoreHud({ activeDevelopments }: Props) {
  const positives = activeDevelopments.filter((dev) => dev.valence === "positive");
  const negatives = activeDevelopments.filter((dev) => dev.valence === "negative");
  const positiveScore = positives.reduce((sum, dev) => sum + Math.max(dev.impact_score, dev.severity), 0);
  const negativeScore = negatives.reduce((sum, dev) => sum + Math.max(Math.abs(dev.impact_score), dev.severity), 0);
  const net = positiveScore - negativeScore;

  return (
    <div className="score">
      <strong>World balance</strong>
      <div className="score__row">
        <span>Positive momentum</span>
        <span>{positiveScore}</span>
      </div>
      <div className="score__row">
        <span>Open strain</span>
        <span>{negativeScore}</span>
      </div>
      <div className="score__row score__row--net">
        <span>Net outlook</span>
        <span>{net}</span>
      </div>
    </div>
  );
}
