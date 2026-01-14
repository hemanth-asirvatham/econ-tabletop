import { useEffect, useMemo, useReducer, useState } from "react";
import { DeckControls } from "./components/DeckControls";
import { EventLog } from "./components/EventLog";
import { PlayerHand } from "./components/PlayerHand";
import { ScoreHud } from "./components/ScoreHud";
import { Table } from "./components/Table";
import { clearState, loadState, saveState } from "./state/persistence";
import { Action, createInitialState, gameReducer } from "./state/gameReducer";
import { DevelopmentCard, GameSettings, PolicyCard } from "./state/types";

const DEFAULT_SETTINGS: GameSettings = {
  players: 4,
  handSize: 5,
  devFaceupStart: 4,
  devFacedownStart: 2,
  devFaceupPerRound: 3,
  devFacedownPerRound: 1,
  policyDrawPerRound: 2,
  maxPoliciesPerRound: 3,
};

const DECK_BASE_URL = "http://localhost:8787";

export default function App() {
  const [state, dispatch] = useReducer(gameReducer, createInitialState(DEFAULT_SETTINGS));
  const [setupReady, setSetupReady] = useState(false);

  const activeDevelopments = useMemo(() => [...state.faceUp, ...state.faceDown], [state.faceUp, state.faceDown]);

  useEffect(() => {
    const saved = loadState();
    if (saved) {
      dispatch({ type: "INIT_DECK", payload: { manifest: saved.manifest || {}, policies: saved.policies, developmentsByStage: saved.developmentsByStage, settings: saved.settings } } as Action);
      setSetupReady(true);
    }
  }, []);

  useEffect(() => {
    if (state.manifest) {
      saveState(state);
    }
  }, [state]);

  async function loadDeck() {
    const [manifestRes, policiesRes, stagesRes] = await Promise.all([
      fetch(`${DECK_BASE_URL}/api/manifest`),
      fetch(`${DECK_BASE_URL}/api/policies`),
      fetch(`${DECK_BASE_URL}/api/stages`),
    ]);
    const manifest = await manifestRes.json();
    const policies = (await policiesRes.json()) as PolicyCard[];
    const { stages } = await stagesRes.json();
    const developmentsByStage: Record<number, DevelopmentCard[]> = {};
    await Promise.all(
      stages.map(async (stage: number) => {
        const res = await fetch(`${DECK_BASE_URL}/api/developments?stage=${stage}`);
        developmentsByStage[stage] = (await res.json()) as DevelopmentCard[];
      }),
    );
    dispatch({ type: "INIT_DECK", payload: { manifest, policies, developmentsByStage, settings: state.settings } });
    setSetupReady(true);
  }

  function updateSettings(partial: Partial<GameSettings>) {
    dispatch({ type: "INIT_DECK", payload: { manifest: state.manifest || {}, policies: state.policies, developmentsByStage: state.developmentsByStage, settings: { ...state.settings, ...partial } } } as Action);
  }

  function resetSession() {
    clearState();
    window.location.reload();
  }

  return (
    <div style={{ background: "#020617", minHeight: "100vh", color: "#e2e8f0", padding: 24 }}>
      <header style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <div>
          <h1 style={{ margin: 0 }}>Econ Tabletop</h1>
          <p style={{ marginTop: 4, color: "#94a3b8" }}>AI/AGI economy simulation</p>
        </div>
        <button onClick={resetSession}>Reset Session</button>
      </header>

      {!setupReady ? (
        <section style={{ marginTop: 24, display: "grid", gap: 16, maxWidth: 640 }}>
          <h2>Setup</h2>
          <button onClick={loadDeck}>Load Deck from Local Server</button>
          <label>
            Players
            <input
              type="number"
              value={state.settings.players}
              onChange={(e) => updateSettings({ players: Number(e.target.value) })}
            />
          </label>
          <label>
            Hand size
            <input
              type="number"
              value={state.settings.handSize}
              onChange={(e) => updateSettings({ handSize: Number(e.target.value) })}
            />
          </label>
        </section>
      ) : (
        <main style={{ marginTop: 24, display: "grid", gap: 24 }}>
          <section style={{ display: "flex", gap: 16, alignItems: "center" }}>
            <DeckControls
              onDeal={() => dispatch({ type: "DEAL_STAGE" })}
              onDrawRound={() => dispatch({ type: "DRAW_ROUND" })}
              onPlayPolicy={() => state.selectedPolicyId && dispatch({ type: "PLAY_POLICY", payload: { policyId: state.selectedPolicyId } })}
              onAttach={() => {
                if (state.selectedPolicyId && state.selectedDevId) {
                  dispatch({ type: "ATTACH_DEV", payload: { policyId: state.selectedPolicyId, devId: state.selectedDevId } });
                }
              }}
              onAutoAttach={() => dispatch({ type: "AUTO_ATTACH" })}
              onAdvance={() => dispatch({ type: "ADVANCE_STAGE" })}
              onUndo={() => dispatch({ type: "UNDO" })}
              onRedo={() => dispatch({ type: "REDO" })}
            />
            <ScoreHud activeDevelopments={activeDevelopments} />
          </section>

          <PlayerHand
            hand={state.hand}
            imageBaseUrl={DECK_BASE_URL}
            selectedPolicyId={state.selectedPolicyId}
            onSelectPolicy={(id) => dispatch({ type: "SELECT_POLICY", payload: { policyId: id } })}
          />

          <Table
            faceUp={state.faceUp}
            faceDown={state.faceDown}
            dormant={state.dormant}
            implemented={state.implemented}
            attachments={state.attachments}
            imageBaseUrl={DECK_BASE_URL}
            selectedDevId={state.selectedDevId}
            selectedPolicyId={state.selectedPolicyId}
            onSelectDev={(id) => dispatch({ type: "SELECT_DEV", payload: { devId: id } })}
            onSelectPolicy={(id) => dispatch({ type: "SELECT_POLICY", payload: { policyId: id } })}
            onAttach={(policyId, devId) => dispatch({ type: "ATTACH_DEV", payload: { policyId, devId } })}
            onPlayPolicy={(policyId) => dispatch({ type: "PLAY_POLICY", payload: { policyId } })}
          />

          <EventLog log={state.log} />
        </main>
      )}
    </div>
  );
}
