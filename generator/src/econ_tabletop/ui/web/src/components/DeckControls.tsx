import { useEffect, useMemo, useState } from "react";

import { DevelopmentCard, PolicyCard } from "../state/types";

type DragPayload = {
  kind: "policy" | "development";
  id: string;
};

type Props = {
  stageIndex: number;
  stageCount: number;
  policyRemaining: number;
  developmentsRemaining: number;
  discardedDevelopments: DevelopmentCard[];
  discardedPolicies: PolicyCard[];
  onDealDevelopments: (stageIndex: number, faceUpCount: number, faceDownCount: number) => void;
  onDrawPolicies: (count: number) => void;
  onDiscard: (payload: DragPayload) => void;
  onAutoAttach: () => void;
  onAdvance: () => void;
  onUndo: () => void;
  onRedo: () => void;
};

function readPayload(event: React.DragEvent): DragPayload | null {
  const raw =
    event.dataTransfer.getData("application/x-econ-tabletop-card") ||
    event.dataTransfer.getData("text/plain");
  if (!raw) return null;
  try {
    const payload = JSON.parse(raw) as DragPayload;
    if (payload && (payload.kind === "policy" || payload.kind === "development")) {
      return payload;
    }
  } catch {
    return null;
  }
  return null;
}

export function DeckControls({
  stageIndex,
  stageCount,
  policyRemaining,
  developmentsRemaining,
  discardedDevelopments,
  discardedPolicies,
  onDealDevelopments,
  onDrawPolicies,
  onDiscard,
  onAutoAttach,
  onAdvance,
  onUndo,
  onRedo,
}: Props) {
  const [devStage, setDevStage] = useState(stageIndex);
  const [devTotal, setDevTotal] = useState(5);
  const [devFaceDown, setDevFaceDown] = useState(2);
  const [policyDraw, setPolicyDraw] = useState(3);
  const faceUpCount = useMemo(() => Math.max(0, devTotal - devFaceDown), [devTotal, devFaceDown]);
  const discardCount = discardedDevelopments.length + discardedPolicies.length;

  useEffect(() => {
    setDevStage(stageIndex);
  }, [stageIndex]);

  return (
    <div className="controls">
      <div className="controls__stage">
        <span>Stage</span>
        <strong>
          {stageIndex + 1} / {stageCount}
        </strong>
      </div>
      <div className="controls__decks">
        <details className="deck">
          <summary className="deck__summary">
            <span className="deck__label">Development Deck</span>
            <span className="deck__meta">{developmentsRemaining} remaining</span>
          </summary>
          <div className="deck__panel">
            <label>
              Stage to deal
              <input
                type="number"
                min={0}
                max={Math.max(0, stageCount - 1)}
                value={devStage}
                onChange={(event) => setDevStage(Number(event.target.value))}
              />
            </label>
            <label>
              Total cards
              <input
                type="number"
                min={0}
                value={devTotal}
                onChange={(event) => {
                  const nextTotal = Math.max(0, Number(event.target.value));
                  setDevTotal(nextTotal);
                  setDevFaceDown(Math.min(devFaceDown, nextTotal));
                }}
              />
            </label>
            <label>
              Face-down
              <input
                type="number"
                min={0}
                value={devFaceDown}
                onChange={(event) => {
                  const nextFaceDown = Math.max(0, Number(event.target.value));
                  setDevFaceDown(Math.min(nextFaceDown, devTotal));
                }}
              />
            </label>
            <div className="deck__row">
              <span>Face-up</span>
              <strong>{faceUpCount}</strong>
            </div>
            <button
              className="btn btn--primary btn--chip"
              onClick={() => onDealDevelopments(devStage, faceUpCount, devFaceDown)}
            >
              Deal Developments
            </button>
          </div>
        </details>

        <details className="deck">
          <summary className="deck__summary">
            <span className="deck__label">Policy Deck</span>
            <span className="deck__meta">{policyRemaining} remaining</span>
          </summary>
          <div className="deck__panel">
            <label>
              Cards to draw
              <input
                type="number"
                min={0}
                value={policyDraw}
                onChange={(event) => setPolicyDraw(Math.max(0, Number(event.target.value)))}
              />
            </label>
            <button className="btn btn--primary btn--chip" onClick={() => onDrawPolicies(policyDraw)}>
              Draw Policies
            </button>
          </div>
        </details>

        <div
          className="deck deck--discard"
          onDragOver={(event) => event.preventDefault()}
          onDrop={(event) => {
            const payload = readPayload(event);
            if (payload) {
              onDiscard(payload);
            }
          }}
        >
          <div className="deck__summary">
            <span className="deck__label">Discard</span>
            <span className="deck__meta">{discardCount} cards</span>
          </div>
          <div className="deck__panel deck__panel--discard">
            <strong>Discarded cards</strong>
            <ul>
              {discardedPolicies.map((policy) => (
                <li key={policy.id}>{policy.title}</li>
              ))}
              {discardedDevelopments.map((dev) => (
                <li key={dev.id}>{dev.title}</li>
              ))}
            </ul>
          </div>
        </div>
      </div>
      <div className="controls__actions">
        <button className="btn btn--chip" onClick={onAutoAttach}>
          Auto-attach
        </button>
        <button className="btn btn--chip" onClick={onAdvance}>
          Advance Stage
        </button>
      </div>
      <div className="controls__history">
        <button className="btn btn--ghost btn--chip" onClick={onUndo}>
          Undo
        </button>
        <button className="btn btn--ghost btn--chip" onClick={onRedo}>
          Redo
        </button>
      </div>
    </div>
  );
}
