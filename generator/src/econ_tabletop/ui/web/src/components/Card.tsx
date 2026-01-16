import { useMemo, useState } from "react";

import { DevelopmentCard, PolicyCard } from "../state/types";

type DragPayload = {
  kind: "policy" | "development";
  id: string;
};

type CardVariant = "full" | "visual" | "compact";

type Props = {
  card: PolicyCard | DevelopmentCard;
  type: "policy" | "development";
  imageBaseUrl: string;
  selected?: boolean;
  dragPayload?: DragPayload;
  onClick?: () => void;
  variant?: CardVariant;
  faceDown?: boolean;
};

function renderInlineMarkdown(text: string) {
  return text
    .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
    .replace(/\*(.+?)\*/g, "<em>$1</em>");
}

export function Card({
  card,
  type,
  imageBaseUrl,
  selected,
  dragPayload,
  onClick,
  variant = "full",
  faceDown = false,
}: Props) {
  const [imageVariant, setImageVariant] = useState<"images" | "render">("images");
  const [imageFailed, setImageFailed] = useState(false);
  const imageSrc = useMemo(() => {
    if (imageFailed || faceDown) return "";
    return `${imageBaseUrl}/${imageVariant}/${type}/${card.id}.png`;
  }, [card.id, faceDown, imageBaseUrl, imageFailed, imageVariant, type]);
  const descriptionHtml = useMemo(() => renderInlineMarkdown(card.short_description), [card.short_description]);

  return (
    <div
      className={`card card--${type} card--${variant}${faceDown ? " card--facedown" : ""}${selected ? " card--selected" : ""}`}
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
        ) : faceDown ? (
          <div className="card__back">
            <span>Face-down</span>
          </div>
        ) : (
          <div className="card__fallback">No image available</div>
        )}
      </div>
      {!faceDown && variant === "full" ? (
        <>
          <div className="card__meta">{type}</div>
          <div className="card__title">{card.title}</div>
          <div className="card__body" dangerouslySetInnerHTML={{ __html: descriptionHtml }} />
        </>
      ) : !faceDown && variant === "visual" ? (
        <div className="card__info">
          <div className="card__meta">{type}</div>
          <div className="card__title">{card.title}</div>
          <div className="card__body" dangerouslySetInnerHTML={{ __html: descriptionHtml }} />
        </div>
      ) : null}
    </div>
  );
}
