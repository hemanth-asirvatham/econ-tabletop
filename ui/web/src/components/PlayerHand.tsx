import { PolicyCard } from "../state/types";
import { Card } from "./Card";

type Props = {
  hand: PolicyCard[];
  selectedPolicyId: string | null;
  onSelectPolicy: (id: string) => void;
};

export function PlayerHand({ hand, selectedPolicyId, onSelectPolicy }: Props) {
  return (
    <section>
      <h3 style={{ color: "#f8fafc" }}>Player Hand</h3>
      <div style={{ display: "flex", gap: 12, flexWrap: "wrap" }}>
        {hand.map((policy) => (
          <Card
            key={policy.id}
            card={policy}
            type="policy"
            selected={selectedPolicyId === policy.id}
            onClick={() => onSelectPolicy(policy.id)}
          />
        ))}
      </div>
    </section>
  );
}
