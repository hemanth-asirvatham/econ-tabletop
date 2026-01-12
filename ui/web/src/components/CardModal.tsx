import { DevelopmentCard, PolicyCard } from "../state/types";

type Props = {
  card: PolicyCard | DevelopmentCard | null;
  onClose: () => void;
};

export function CardModal({ card, onClose }: Props) {
  if (!card) return null;
  return (
    <div
      style={{
        position: "fixed",
        inset: 0,
        background: "rgba(15, 23, 42, 0.8)",
        display: "grid",
        placeItems: "center",
      }}
      onClick={onClose}
    >
      <div style={{ background: "#0f172a", padding: 24, borderRadius: 12, maxWidth: 640 }}>
        <h2 style={{ color: "#f8fafc" }}>{card.title}</h2>
        <p style={{ color: "#e2e8f0" }}>{card.description}</p>
        <button onClick={onClose}>Close</button>
      </div>
    </div>
  );
}
