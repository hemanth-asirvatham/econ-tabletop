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
    <div className="score">
      <strong>Score</strong>
      <div className="score__row">
        <span>Active positives</span>
        <span>{positiveScore}</span>
      </div>
      <div className="score__row">
        <span>Active negatives</span>
        <span>{negativeScore}</span>
      </div>
      <div className="score__row score__row--net">
        <span>Net score</span>
        <span>{net}</span>
      </div>
    </div>
  );
}
