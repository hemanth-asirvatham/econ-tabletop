import { useMemo, useState } from "react";

import { DevelopmentCard, PolicyCard } from "../state/types";

type DragPayload = {
  kind: "policy" | "development";
  id: string;
};

type Props = {
  card: PolicyCard | DevelopmentCard;
  type: "policy" | "development";
  imageBaseUrl: string;
  selected?: boolean;
  dragPayload?: DragPayload;
  onClick?: () => void;
};

export function Card({ card, type, imageBaseUrl, selected, dragPayload, onClick }: Props) {
  const [imageVariant, setImageVariant] = useState<"images" | "render">("images");
  const [imageFailed, setImageFailed] = useState(false);
  const imageSrc = useMemo(() => {
    if (imageFailed) return "";
    return `${imageBaseUrl}/${imageVariant}/${type}/${card.id}.png`;
  }, [card.id, imageBaseUrl, imageFailed, imageVariant, type]);

  return (
    <div
      onClick={onClick}
      draggable={Boolean(dragPayload)}
      onDragStart={(event) => {
        if (!dragPayload) return;
        const payload = JSON.stringify(dragPayload);
        event.dataTransfer.setData("application/x-econ-tabletop-card", payload);
        event.dataTransfer.setData("text/plain", payload);
        event.dataTransfer.effectAllowed = "move";
      }}
      style={{
        border: selected ? "2px solid #7dd3fc" : "1px solid #334155",
        borderRadius: 8,
        padding: 12,
        background: "#0f172a",
        color: "#e2e8f0",
        cursor: "pointer",
        width: 240,
        display: "grid",
        gap: 8,
        boxShadow: selected ? "0 0 0 2px rgba(125, 211, 252, 0.4)" : "0 6px 16px rgba(15, 23, 42, 0.45)",
      }}
    >
      <div
        style={{
          borderRadius: 6,
          overflow: "hidden",
          border: "1px solid rgba(148, 163, 184, 0.3)",
          background: "linear-gradient(135deg, rgba(30, 41, 59, 0.9), rgba(15, 23, 42, 0.9))",
          aspectRatio: "16 / 9",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
        }}
      >
        {imageSrc ? (
          <img
            src={imageSrc}
            alt={card.title}
            loading="lazy"
            onError={() => {
              if (imageVariant === "images") {
                setImageVariant("render");
              } else {
                setImageFailed(true);
              }
            }}
            style={{ width: "100%", height: "100%", objectFit: "cover", display: "block" }}
          />
        ) : (
          <div style={{ fontSize: 12, color: "#94a3b8", padding: 12, textAlign: "center" }}>No image available</div>
        )}
      </div>
      <div style={{ fontSize: 11, textTransform: "uppercase", color: "#94a3b8", letterSpacing: 0.8 }}>{type}</div>
      <div style={{ fontWeight: 700 }}>{card.title}</div>
      <div style={{ fontSize: 12, color: "#cbd5f5" }}>{card.short_description}</div>
    </div>
  );
}
