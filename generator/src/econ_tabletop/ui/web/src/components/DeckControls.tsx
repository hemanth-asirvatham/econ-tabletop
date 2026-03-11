import { useEffect, useMemo, useState } from "react";

import { DevelopmentCard, PolicyCard } from "../state/types";

type DragPayload = {
  kind: "policy" | "development";
  id: string;
};

type Props = {
  started: boolean;
  stageIndex: number;
  stageCount: number;
  policyRemaining: number;
  developmentsRemaining: number;
  budgetRemaining: number;
  budgetTotal: number;
  discardedDevelopments: DevelopmentCard[];
  discardedPolicies: PolicyCard[];
  onStartGame: () => void;
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
  started,
  stageIndex,
  stageCount,
  policyRemaining,
  developmentsRemaining,
  budgetRemaining,
  budgetTotal,
  discardedDevelopments,
  discardedPolicies,
  onStartGame,
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
  const [policyDraw, setPolicyDraw] = useState(5);
  const faceUpCount = useMemo(() => Math.max(0, devTotal - devFaceDown), [devTotal, devFaceDown]);
  const discardCount = discardedDevelopments.length + discardedPolicies.length;

  useEffect(() => {
    setDevStage(stageIndex);
  }, [stageIndex]);

  return (
    <div className="controls">
      <div className="controls__hero">
        <div>
          <p className="controls__eyebrow">Stage controls</p>
          <h2>{started ? `Stage ${stageIndex + 1} of ${stageCount}` : "Load the deck, then start the simulation"}</h2>
          <p>
            {started
              ? "Policies stay in play across stages. Face-down developments flip forward automatically when you advance."
              : "The default start deals 10 policies and 5 developments (3 face-up, 2 face-down)."}
          </p>
        </div>
        <div className="controls__budget">
          <span>Stage budget</span>
          <strong>
            ${budgetRemaining} / ${budgetTotal}
          </strong>
        </div>
      </div>

      <div className="controls__actions">
        {!started ? (
          <button className="btn btn--primary" onClick={onStartGame}>
            Start simulation
          </button>
        ) : (
          <button className="btn btn--primary" onClick={onAdvance}>
            Advance to next stage
          </button>
        )}
        <button className="btn btn--secondary" onClick={onAutoAttach} disabled={!started}>
          Auto-attach conditionals
        </button>
        <button className="btn btn--ghost" onClick={onUndo}>
          Undo
        </button>
        <button className="btn btn--ghost" onClick={onRedo}>
          Redo
        </button>
      </div>

      <div className="controls__manual">
        <div className="controls__panel">
          <div className="controls__panel-header">
            <span>Policy deck</span>
            <strong>{policyRemaining} remaining</strong>
          </div>
          <label className="field">
            <span>Cards to draw</span>
            <input
              type="number"
              min={0}
              value={policyDraw}
              onChange={(event) => setPolicyDraw(Math.max(0, Number(event.target.value)))}
            />
          </label>
          <button className="btn btn--secondary" onClick={() => onDrawPolicies(policyDraw)} disabled={!started}>
            Draw policies
          </button>
        </div>

        <div className="controls__panel">
          <div className="controls__panel-header">
            <span>Development deck</span>
            <strong>{developmentsRemaining} remaining</strong>
          </div>
          <label className="field">
            <span>Stage to deal</span>
            <input
              type="number"
              min={0}
              max={Math.max(0, stageCount - 1)}
              value={devStage}
              onChange={(event) => setDevStage(Number(event.target.value))}
            />
          </label>
          <div className="controls__inline-fields">
            <label className="field">
              <span>Total</span>
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
            <label className="field">
              <span>Face-down</span>
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
          </div>
          <p className="controls__microcopy">Manual deal: {faceUpCount} face-up, {devFaceDown} face-down.</p>
          <button
            className="btn btn--secondary"
            onClick={() => onDealDevelopments(devStage, faceUpCount, devFaceDown)}
            disabled={!started}
          >
            Deal developments
          </button>
        </div>

        <div
          className="controls__panel controls__panel--discard"
          onDragOver={(event) => event.preventDefault()}
          onDrop={(event) => {
            const payload = readPayload(event);
            if (payload) {
              onDiscard(payload);
            }
          }}
        >
          <div className="controls__panel-header">
            <span>Discard</span>
            <strong>{discardCount} cards</strong>
          </div>
          <p className="controls__microcopy">Drag any policy or development card here to remove it from play.</p>
          <div className="controls__discard-list">
            {discardedPolicies.map((policy) => (
              <span key={policy.id}>{policy.title}</span>
            ))}
            {discardedDevelopments.map((dev) => (
              <span key={dev.id}>{dev.title}</span>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
