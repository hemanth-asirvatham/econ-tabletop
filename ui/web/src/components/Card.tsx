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
      className={`card card--${type}${selected ? " card--selected" : ""}`}
      onClick={onClick}
      draggable={Boolean(dragPayload)}
      onDragStart={(event) => {
        if (!dragPayload) return;
        const payload = JSON.stringify(dragPayload);
        event.dataTransfer.setData("application/x-econ-tabletop-card", payload);
        event.dataTransfer.setData("text/plain", payload);
        event.dataTransfer.effectAllowed = "move";
      }}
    >
      <div className="card__art">
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
            className="card__image"
          />
        ) : (
          <div className="card__fallback">No image available</div>
        )}
      </div>
      <div className="card__meta">{type}</div>
      <div className="card__title">{card.title}</div>
      <div className="card__body">{card.short_description}</div>
    </div>
  );
}
