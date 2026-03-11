import { useEffect, useMemo, useReducer, useState } from "react";
import { CardModal } from "./components/CardModal";
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
  handSize: 10,
  devFaceupStart: 3,
  devFacedownStart: 2,
  devFaceupPerRound: 3,
  devFacedownPerRound: 2,
  policyDrawPerRound: 5,
  maxPoliciesPerRound: 3,
  budgetPerStage: 5,
};

const DECK_BASE_URL = "http://localhost:8787";

function settingsFromManifest(manifest: Record<string, unknown> | null): GameSettings {
  const gameplayDefaults = ((manifest?.gameplay_defaults as Record<string, unknown> | undefined) ?? {});
  return {
    players: Number(gameplayDefaults.players_default ?? DEFAULT_SETTINGS.players),
    handSize: Number(gameplayDefaults.hand_size_start ?? DEFAULT_SETTINGS.handSize),
    devFaceupStart: Number(gameplayDefaults.dev_faceup_start ?? DEFAULT_SETTINGS.devFaceupStart),
    devFacedownStart: Number(gameplayDefaults.dev_facedown_start ?? DEFAULT_SETTINGS.devFacedownStart),
    devFaceupPerRound: Number(gameplayDefaults.dev_faceup_per_round ?? DEFAULT_SETTINGS.devFaceupPerRound),
    devFacedownPerRound: Number(gameplayDefaults.dev_facedown_per_round ?? DEFAULT_SETTINGS.devFacedownPerRound),
    policyDrawPerRound: Number(gameplayDefaults.policy_draw_per_round ?? DEFAULT_SETTINGS.policyDrawPerRound),
    maxPoliciesPerRound: Number(
      gameplayDefaults.max_policies_per_player_per_round ?? DEFAULT_SETTINGS.maxPoliciesPerRound,
    ),
    budgetPerStage: Number(gameplayDefaults.budget_per_stage ?? DEFAULT_SETTINGS.budgetPerStage),
  };
}

export default function App() {
  const [state, dispatch] = useReducer(gameReducer, createInitialState(DEFAULT_SETTINGS));
  const [setupReady, setSetupReady] = useState(false);
  const [modalState, setModalState] = useState<{ type: "policy" | "development"; id: string } | null>(null);

  const activeDevelopments = useMemo(() => state.faceUp, [state.faceUp]);
  const stageCount = useMemo(() => Object.keys(state.developmentsByStage).length || 1, [state.developmentsByStage]);
  const stageDeckCount = useMemo(
    () => (state.developmentsByStage[state.stageIndex] || []).length,
    [state.developmentsByStage, state.stageIndex],
  );
  const developmentsRemaining = useMemo(() => {
    const used = state.developmentDrawIndexByStage[state.stageIndex] || 0;
    return Math.max(0, stageDeckCount - used);
  }, [state.developmentDrawIndexByStage, stageDeckCount, state.stageIndex]);
  const budgetRemaining = useMemo(
    () => Math.max(0, state.settings.budgetPerStage - state.budgetSpentThisStage),
    [state.budgetSpentThisStage, state.settings.budgetPerStage],
  );
  const policyModalCards = useMemo(() => {
    const merged = [...state.hand, ...state.implemented];
    const seen = new Set<string>();
    return merged.filter((card) => {
      if (seen.has(card.id)) return false;
      seen.add(card.id);
      return true;
    });
  }, [state.hand, state.implemented]);
  const developmentModalCards = useMemo(() => {
    const merged = [...state.faceUp, ...state.faceDown, ...Object.values(state.attachments).flat()];
    const seen = new Set<string>();
    return merged.filter((card) => {
      if (seen.has(card.id)) return false;
      seen.add(card.id);
      return true;
    });
  }, [state.attachments, state.faceDown, state.faceUp]);
  const modalCards = modalState?.type === "policy" ? policyModalCards : developmentModalCards;
  const modalCard = useMemo(() => {
    if (!modalState) return null;
    const list = modalState.type === "policy" ? policyModalCards : developmentModalCards;
    return list.find((card) => card.id === modalState.id) ?? null;
  }, [developmentModalCards, modalState, policyModalCards]);
  const scenarioName = String((state.manifest?.scenario as Record<string, unknown> | undefined)?.name ?? "Econ Tabletop");

  useEffect(() => {
    const saved = loadState();
    if (saved) {
      dispatch({ type: "HYDRATE", payload: saved });
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
    const manifest = (await manifestRes.json()) as Record<string, unknown>;
    const policies = (await policiesRes.json()) as PolicyCard[];
    const { stages } = (await stagesRes.json()) as { stages: number[] };
    const developmentsByStage: Record<number, DevelopmentCard[]> = {};
    await Promise.all(
      stages.map(async (stage: number) => {
        const res = await fetch(`${DECK_BASE_URL}/api/developments?stage=${stage}`);
        developmentsByStage[stage] = (await res.json()) as DevelopmentCard[];
      }),
    );
    dispatch({
      type: "INIT_DECK",
      payload: {
        manifest,
        policies,
        developmentsByStage,
        settings: settingsFromManifest(manifest),
      },
    });
    setSetupReady(true);
  }

  function updateSettings(partial: Partial<GameSettings>) {
    dispatch({
      type: "INIT_DECK",
      payload: {
        manifest: state.manifest || {},
        policies: state.policies,
        developmentsByStage: state.developmentsByStage,
        settings: { ...state.settings, ...partial },
      },
    } as Action);
  }

  function resetSession() {
    clearState();
    window.location.reload();
  }

  return (
    <div className="app">
      <div className="app__backdrop" />
      <header className="app__header">
        <div className="app__branding">
          <span className="app__eyebrow">Economic futures simulator</span>
          <h1>{scenarioName}</h1>
          <p>Readable AI economy storytelling with budgeted policy tradeoffs.</p>
        </div>
        <div className="app__header-actions">
          <button className="btn btn--ghost" onClick={resetSession}>
            Reset session
          </button>
        </div>
      </header>

      {!setupReady ? (
        <section className="setup">
          <div className="setup__panel">
            <p className="setup__eyebrow">Local deck server</p>
            <h2>Load a generated deck</h2>
            <p>
              The interface expects a generated deck from the local server, then lets you run the default stage flow or
              use manual house rules.
            </p>
            <button className="btn btn--primary" onClick={loadDeck}>
              Load deck from local server
            </button>
          </div>
          <div className="setup__panel">
            <p className="setup__eyebrow">Fallback defaults</p>
            <h2>Baseline rules</h2>
            <div className="setup__fields">
              <label className="field">
                <span>Players</span>
                <input
                  type="number"
                  value={state.settings.players}
                  onChange={(e) => updateSettings({ players: Number(e.target.value) })}
                />
              </label>
              <label className="field">
                <span>Stage budget</span>
                <input
                  type="number"
                  value={state.settings.budgetPerStage}
                  onChange={(e) => updateSettings({ budgetPerStage: Number(e.target.value) })}
                />
              </label>
              <label className="field">
                <span>Starting hand</span>
                <input
                  type="number"
                  value={state.settings.handSize}
                  onChange={(e) => updateSettings({ handSize: Number(e.target.value) })}
                />
              </label>
            </div>
          </div>
        </section>
      ) : (
        <main className="app__main">
          <section className="dashboard">
            <div className="dashboard__hero">
              <div className="dashboard__stat">
                <span>Stage</span>
                <strong>
                  {state.stageIndex + 1} / {stageCount}
                </strong>
              </div>
              <div className="dashboard__stat">
                <span>Budget left</span>
                <strong>${budgetRemaining}</strong>
              </div>
              <div className="dashboard__stat">
                <span>Policies in hand</span>
                <strong>{state.hand.length}</strong>
              </div>
              <div className="dashboard__stat">
                <span>Policies in play</span>
                <strong>{state.implemented.length}</strong>
              </div>
            </div>
            <div className="dashboard__sidebar">
              <ScoreHud activeDevelopments={activeDevelopments} />
            </div>
          </section>

          <section className="panel">
            <DeckControls
              started={state.round > 0}
              stageIndex={state.stageIndex}
              stageCount={stageCount}
              policyRemaining={state.policyDeck.length}
              developmentsRemaining={developmentsRemaining}
              budgetRemaining={budgetRemaining}
              budgetTotal={state.settings.budgetPerStage}
              discardedDevelopments={state.discardedDevelopments}
              discardedPolicies={state.discardedPolicies}
              onStartGame={() => dispatch({ type: "START_GAME" })}
              onDealDevelopments={(stageIndex, faceUpCount, faceDownCount) =>
                dispatch({ type: "DEAL_DEVELOPMENTS", payload: { stageIndex, faceUpCount, faceDownCount } })
              }
              onDrawPolicies={(count) => dispatch({ type: "DRAW_POLICIES", payload: { count } })}
              onDiscard={(payload) => dispatch({ type: "DISCARD_CARD", payload })}
              onAutoAttach={() => dispatch({ type: "AUTO_ATTACH" })}
              onAdvance={() => dispatch({ type: "ADVANCE_STAGE" })}
              onUndo={() => dispatch({ type: "UNDO" })}
              onRedo={() => dispatch({ type: "REDO" })}
            />
          </section>

          <section className="panel panel--board">
            <div className="panel__header panel__header--board">
              <div>
                <p className="panel__eyebrow">Board state</p>
                <h2>World events and policy responses</h2>
                <p>
                  Most development cards simply describe the world. Drag them under a policy only when the table agrees
                  the policy meaningfully addresses that story.
                </p>
              </div>
            </div>
            <Table
              faceUp={state.faceUp}
              faceDown={state.faceDown}
              implemented={state.implemented}
              attachments={state.attachments}
              imageBaseUrl={DECK_BASE_URL}
              selectedDevId={state.selectedDevId}
              selectedPolicyId={state.selectedPolicyId}
              onSelectDev={(id) => dispatch({ type: "SELECT_DEV", payload: { devId: id } })}
              onSelectPolicy={(id) => dispatch({ type: "SELECT_POLICY", payload: { policyId: id } })}
              onInspectDev={(card) => setModalState({ type: "development", id: card.id })}
              onInspectPolicy={(card) => setModalState({ type: "policy", id: card.id })}
              onAttach={(policyId, devId) => dispatch({ type: "ATTACH_DEV", payload: { policyId, devId } })}
              onPlayPolicy={(policyId) => dispatch({ type: "PLAY_POLICY", payload: { policyId } })}
            />
          </section>

          <section className="app__lower">
            <section className="panel panel--hand">
              <PlayerHand
                hand={state.hand}
                imageBaseUrl={DECK_BASE_URL}
                selectedPolicyId={state.selectedPolicyId}
                onSelectPolicy={(id) => dispatch({ type: "SELECT_POLICY", payload: { policyId: id } })}
                onInspectPolicy={(card) => setModalState({ type: "policy", id: card.id })}
              />
            </section>

            <section className="panel panel--log">
              <EventLog log={state.log} />
            </section>
          </section>
        </main>
      )}
      {modalState && modalCard ? (
        <CardModal
          card={modalCard}
          cards={modalCards}
          cardType={modalState.type}
          imageBaseUrl={DECK_BASE_URL}
          onClose={() => setModalState(null)}
        />
      ) : null}
    </div>
  );
}
