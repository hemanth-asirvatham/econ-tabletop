import { useEffect, useMemo, useState } from "react";

import { DevelopmentCard, PolicyCard } from "../state/types";

type Props = {
  card: PolicyCard | DevelopmentCard | null;
  cards: Array<PolicyCard | DevelopmentCard>;
  cardType: "policy" | "development";
  imageBaseUrl: string;
  onClose: () => void;
};

function isDevelopmentCard(card: PolicyCard | DevelopmentCard): card is DevelopmentCard {
  return "stage" in card;
}

export function CardModal({ card, cards, cardType, imageBaseUrl, onClose }: Props) {
  const [activeIndex, setActiveIndex] = useState(0);
  const [imageVariant, setImageVariant] = useState<"images" | "render">("images");
  const [imageFailed, setImageFailed] = useState(false);

  useEffect(() => {
    if (!card) return;
    const index = cards.findIndex((item) => item.id === card.id);
    setActiveIndex(index >= 0 ? index : 0);
  }, [card, cards]);

  const activeCard = useMemo(() => {
    if (!card) return null;
    return cards[activeIndex] ?? card;
  }, [activeIndex, card, cards]);

  useEffect(() => {
    setImageVariant("images");
    setImageFailed(false);
  }, [activeCard?.id, cardType]);

  useEffect(() => {
    if (!activeCard) return;
    function handleKey(event: KeyboardEvent) {
      if (event.key === "Escape") {
        onClose();
        return;
      }
      if (event.key === "ArrowLeft") {
        setActiveIndex((prev) => Math.max(prev - 1, 0));
        return;
      }
      if (event.key === "ArrowRight") {
        setActiveIndex((prev) => Math.min(prev + 1, cards.length - 1));
      }
    }
    window.addEventListener("keydown", handleKey);
    return () => window.removeEventListener("keydown", handleKey);
  }, [activeCard, cards.length, onClose]);

  const imageSrc = useMemo(() => {
    if (!activeCard || imageFailed) return "";
    return `${imageBaseUrl}/${imageVariant}/${cardType}/${activeCard.id}.png`;
  }, [activeCard, cardType, imageBaseUrl, imageFailed, imageVariant]);

  if (!activeCard) return null;

  const canGoPrev = activeIndex > 0;
  const canGoNext = activeIndex < cards.length - 1;
  const developmentInstruction =
    isDevelopmentCard(activeCard) && activeCard.rule_box_text ? activeCard.rule_box_text : null;

  return (
    <div className="card-modal" onClick={onClose}>
      <div className="card-modal__content" onClick={(event) => event.stopPropagation()}>
        <div className="card-modal__header">
          <div>
            <p className="card-modal__eyebrow">
              {cardType} card · {activeIndex + 1} / {Math.max(cards.length, 1)}
            </p>
            <h2>{activeCard.title}</h2>
          </div>
          <button className="btn btn--ghost" onClick={onClose}>
            Close
          </button>
        </div>
        <div className="card-modal__body">
          <button
            className="card-modal__nav card-modal__nav--prev"
            onClick={() => setActiveIndex((prev) => Math.max(prev - 1, 0))}
            disabled={!canGoPrev}
            aria-label="Previous card"
          >
            ←
          </button>
          <div className="card-modal__image-frame">
            {imageSrc ? (
              <img
                src={imageSrc}
                alt={activeCard.title}
                onError={() => {
                  if (imageVariant === "images") {
                    setImageVariant("render");
                  } else {
                    setImageFailed(true);
                  }
                }}
              />
            ) : (
              <div className="card-modal__fallback">
                <h3>{activeCard.title}</h3>
                <p>{activeCard.description}</p>
                {developmentInstruction && <p className="card-modal__instruction">{developmentInstruction}</p>}
              </div>
            )}
          </div>
          <button
            className="card-modal__nav card-modal__nav--next"
            onClick={() => setActiveIndex((prev) => Math.min(prev + 1, cards.length - 1))}
            disabled={!canGoNext}
            aria-label="Next card"
          >
            →
          </button>
        </div>
        {developmentInstruction ? (
          <p className="card-modal__instruction">{developmentInstruction}</p>
        ) : (
          <p className="card-modal__hint">Use ← / → to browse. Press Esc to close.</p>
        )}
      </div>
    </div>
  );
}
