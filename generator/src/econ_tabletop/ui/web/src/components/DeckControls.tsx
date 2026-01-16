type Props = {
  onDeal: () => void;
  onDrawRound: () => void;
  onPlayPolicy: () => void;
  onAttach: () => void;
  onAutoAttach: () => void;
  onAdvance: () => void;
  onUndo: () => void;
  onRedo: () => void;
};

export function DeckControls({
  onDeal,
  onDrawRound,
  onPlayPolicy,
  onAttach,
  onAutoAttach,
  onAdvance,
  onUndo,
  onRedo,
}: Props) {
  return (
    <div className="controls">
      <button className="btn btn--primary" onClick={onDeal}>
        Deal Stage
      </button>
      <button className="btn btn--primary" onClick={onDrawRound}>
        Draw Round
      </button>
      <button className="btn" onClick={onPlayPolicy}>
        Play Selected Policy
      </button>
      <button className="btn" onClick={onAttach}>
        Attach Selected Development
      </button>
      <button className="btn" onClick={onAutoAttach}>
        Auto-attach eligible
      </button>
      <button className="btn" onClick={onAdvance}>
        Advance Stage
      </button>
      <button className="btn btn--ghost" onClick={onUndo}>
        Undo
      </button>
      <button className="btn btn--ghost" onClick={onRedo}>
        Redo
      </button>
    </div>
  );
}
