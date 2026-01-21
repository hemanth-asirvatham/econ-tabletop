import { PolicyCard } from "../state/types";
import { Card } from "./Card";

type Props = {
  hand: PolicyCard[];
  imageBaseUrl: string;
  selectedPolicyId: string | null;
  onSelectPolicy: (id: string) => void;
  onInspectPolicy: (card: PolicyCard) => void;
  className?: string;
};

export function PlayerHand({
  hand,
  imageBaseUrl,
  selectedPolicyId,
  onSelectPolicy,
  onInspectPolicy,
  className,
}: Props) {
  return (
    <section className={className ? `hand ${className}` : "hand"}>
      <div className="hand__header">
        <h3>Player Hand</h3>
        <p>Drag a policy card into the table center to implement it.</p>
      </div>
      <div className="hand__cards">
        {hand.map((policy) => (
          <Card
            key={policy.id}
            card={policy}
            type="policy"
            imageBaseUrl={imageBaseUrl}
            variant="visual"
            selected={selectedPolicyId === policy.id}
            dragPayload={{ kind: "policy", id: policy.id }}
            onClick={() => {
              onSelectPolicy(policy.id);
              onInspectPolicy(policy);
            }}
          />
        ))}
      </div>
    </section>
  );
}
