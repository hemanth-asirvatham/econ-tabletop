import { DevelopmentCard, PolicyCard } from "../state/types";
import { Card } from "./Card";

type Props = {
  faceUp: DevelopmentCard[];
  faceDown: DevelopmentCard[];
  dormant: DevelopmentCard[];
  implemented: PolicyCard[];
  attachments: Record<string, DevelopmentCard[]>;
  selectedDevId: string | null;
  selectedPolicyId: string | null;
  onSelectDev: (id: string) => void;
  onSelectPolicy: (id: string) => void;
};

export function Table({
  faceUp,
  faceDown,
  dormant,
  implemented,
  attachments,
  selectedDevId,
  selectedPolicyId,
  onSelectDev,
  onSelectPolicy,
}: Props) {
  return (
    <div style={{ display: "grid", gap: 24 }}>
      <Lane title="Face-up Developments">
        {faceUp.map((dev) => (
          <Card key={dev.id} card={dev} type="development" selected={selectedDevId === dev.id} onClick={() => onSelectDev(dev.id)} />
        ))}
      </Lane>
      <Lane title="Face-down Developments">
        {faceDown.map((dev) => (
          <Card key={dev.id} card={dev} type="development" selected={selectedDevId === dev.id} onClick={() => onSelectDev(dev.id)} />
        ))}
      </Lane>
      <Lane title="Dormant Developments">
        {dormant.map((dev) => (
          <Card key={dev.id} card={dev} type="development" selected={selectedDevId === dev.id} onClick={() => onSelectDev(dev.id)} />
        ))}
      </Lane>
      <Lane title="Implemented Policies">
        {implemented.map((policy) => (
          <div key={policy.id} style={{ display: "grid", gap: 8 }}>
            <Card
              card={policy}
              type="policy"
              selected={selectedPolicyId === policy.id}
              onClick={() => onSelectPolicy(policy.id)}
            />
            <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
              {(attachments[policy.id] || []).map((dev) => (
                <Card key={dev.id} card={dev} type="development" />
              ))}
            </div>
          </div>
        ))}
      </Lane>
    </div>
  );
}

function Lane({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section>
      <h3 style={{ color: "#f8fafc" }}>{title}</h3>
      <div style={{ display: "flex", gap: 12, flexWrap: "wrap" }}>{children}</div>
    </section>
  );
}
