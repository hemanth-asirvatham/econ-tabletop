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
    <div className="app">
      <header className="app__header">
        <div className="app__branding">
          <span className="app__eyebrow">Tabletop Simulation</span>
          <h1>Econ Tabletop</h1>
          <p>AI/AGI economy simulation · tactile policy play</p>
        </div>
        <div className="app__header-actions">
          <button className="btn btn--ghost" onClick={resetSession}>
            Reset Session
          </button>
        </div>
      </header>

      {!setupReady ? (
        <section className="panel panel--setup">
          <div className="panel__header">
            <h2>Setup</h2>
            <p>Load the card deck and tune the baseline round settings.</p>
          </div>
          <div className="panel__body panel__body--stack">
            <button className="btn btn--primary" onClick={loadDeck}>
              Load Deck from Local Server
            </button>
            <label className="field">
              <span>Players</span>
              <input
                type="number"
                value={state.settings.players}
                onChange={(e) => updateSettings({ players: Number(e.target.value) })}
              />
            </label>
            <label className="field">
              <span>Hand size</span>
              <input
                type="number"
                value={state.settings.handSize}
                onChange={(e) => updateSettings({ handSize: Number(e.target.value) })}
              />
            </label>
          </div>
        </section>
      ) : (
        <main className="app__main">
          <aside className="panel panel--controls">
            <div className="panel__header">
              <h2>Round Controls</h2>
              <p>Deal, draw, and advance the stage.</p>
            </div>
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
          </aside>

          <section className="tabletop">
            <div className="tabletop__header">
              <h2>Policy Table</h2>
              <p>Drag policy cards from your hand, then attach development cards to active policies.</p>
            </div>
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
          </section>

          <aside className="panel panel--log">
            <EventLog log={state.log} />
          </aside>

          <section className="panel panel--hand">
            <PlayerHand
              hand={state.hand}
              imageBaseUrl={DECK_BASE_URL}
              selectedPolicyId={state.selectedPolicyId}
              onSelectPolicy={(id) => dispatch({ type: "SELECT_POLICY", payload: { policyId: id } })}
            />
          </section>
        </main>
      )}
    </div>
  );
}
