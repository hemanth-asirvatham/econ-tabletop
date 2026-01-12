import { DevelopmentCard, PolicyCard } from "../state/types";

type Props = {
  card: PolicyCard | DevelopmentCard;
  type: "policy" | "development";
  selected?: boolean;
  onClick?: () => void;
};

export function Card({ card, type, selected, onClick }: Props) {
  return (
    <div
      onClick={onClick}
      style={{
        border: selected ? "2px solid #7dd3fc" : "1px solid #334155",
        borderRadius: 8,
        padding: 12,
        background: "#0f172a",
        color: "#e2e8f0",
        cursor: "pointer",
        width: 220,
      }}
    >
      <div style={{ fontSize: 12, textTransform: "uppercase", color: "#94a3b8" }}>{type}</div>
      <div style={{ fontWeight: 700, marginBottom: 6 }}>{card.title}</div>
      <div style={{ fontSize: 12 }}>{card.short_description}</div>
    </div>
  );
}
