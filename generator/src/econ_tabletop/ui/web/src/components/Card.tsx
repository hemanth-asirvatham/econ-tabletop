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

function isDevelopmentCard(card: PolicyCard | DevelopmentCard): card is DevelopmentCard {
  return "stage" in card;
}

function budgetCost(card: PolicyCard) {
  return card.cost?.budget_cost ?? card.cost?.budget_level ?? 2;
}

function impactRating(card: PolicyCard) {
  return card.impact_rating ?? card.political_capital ?? 3;
}

function arrowSummary(card: DevelopmentCard) {
  if (card.card_type === "power") return "POWER";
  if (card.arrows_up > 0) return "↑".repeat(card.arrows_up);
  if (card.arrows_down > 0) return "↓".repeat(card.arrows_down);
  return "—";
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
  const detailHtml = useMemo(() => renderInlineMarkdown(card.description), [card.description]);
  const devCard = isDevelopmentCard(card) ? card : null;
  const policyCard = !isDevelopmentCard(card) ? card : null;

  return (
    <article
      className={`card card--${type} card--${variant}${faceDown ? " card--facedown" : ""}${selected ? " card--selected" : ""}`}
      onClick={onClick}
      draggable={Boolean(dragPayload && !faceDown)}
      onDragStart={(event) => {
        if (!dragPayload || faceDown) return;
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
            <span>Future shock</span>
          </div>
        ) : (
          <div className="card__fallback">
            <div className="card__fallback-title">{card.title}</div>
            <div className="card__fallback-body" dangerouslySetInnerHTML={{ __html: detailHtml }} />
          </div>
        )}
      </div>
      {!faceDown ? (
        <div className="card__overlay">
          <div className="card__chips">
            {policyCard ? (
              <>
                <span className="card__chip">${budgetCost(policyCard)}</span>
                <span className="card__chip">{policyCard.timeline.time_to_impact}</span>
                <span className="card__chip">Impact {impactRating(policyCard)}</span>
              </>
            ) : devCard ? (
              <>
                <span className="card__chip">Stage {devCard.stage + 1}</span>
                <span className={`card__chip card__chip--${devCard.card_type === "power" ? "power" : devCard.valence}`}>
                  {arrowSummary(devCard)}
                </span>
              </>
            ) : null}
          </div>
          <div className="card__text">
            <div className="card__meta">{type}</div>
            <div className="card__title">{card.title}</div>
            {variant !== "compact" ? (
              <div className="card__body" dangerouslySetInnerHTML={{ __html: descriptionHtml }} />
            ) : null}
          </div>
        </div>
      ) : null}
    </article>
  );
}
