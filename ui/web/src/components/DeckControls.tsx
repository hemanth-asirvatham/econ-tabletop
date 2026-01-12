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
    <div style={{ display: "flex", gap: 12, flexWrap: "wrap" }}>
      <button onClick={onDeal}>Deal Stage</button>
      <button onClick={onDrawRound}>Draw Round</button>
      <button onClick={onPlayPolicy}>Play Selected Policy</button>
      <button onClick={onAttach}>Attach Selected Development</button>
      <button onClick={onAutoAttach}>Auto-attach eligible</button>
      <button onClick={onAdvance}>Advance Stage</button>
      <button onClick={onUndo}>Undo</button>
      <button onClick={onRedo}>Redo</button>
    </div>
  );
}
