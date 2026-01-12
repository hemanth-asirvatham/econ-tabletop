import { DevelopmentCard, GameSettings, GameState, GameStateSnapshot, PolicyCard } from "./types";

export type Action =
  | { type: "INIT_DECK"; payload: { manifest: Record<string, unknown>; policies: PolicyCard[]; developmentsByStage: Record<number, DevelopmentCard[]>; settings: GameSettings } }
  | { type: "DEAL_STAGE" }
  | { type: "DRAW_ROUND" }
  | { type: "PLAY_POLICY"; payload: { policyId: string } }
  | { type: "ATTACH_DEV"; payload: { policyId: string; devId: string } }
  | { type: "AUTO_ATTACH" }
  | { type: "SELECT_DEV"; payload: { devId: string | null } }
  | { type: "SELECT_POLICY"; payload: { policyId: string | null } }
  | { type: "ADVANCE_STAGE" }
  | { type: "UNDO" }
  | { type: "REDO" };

export function createInitialState(settings: GameSettings): GameState {
  return {
    manifest: null,
    stageIndex: 0,
    round: 0,
    policies: [],
    developmentsByStage: {},
    deckOrder: [],
    policyDeck: [],
    faceUp: [],
    faceDown: [],
    dormant: [],
    implemented: [],
    hand: [],
    attachments: {},
    log: [],
    selectedDevId: null,
    selectedPolicyId: null,
    history: [],
    future: [],
    settings,
  };
}

export function gameReducer(state: GameState, action: Action): GameState {
  switch (action.type) {
    case "INIT_DECK": {
      const snapshot = createSnapshot(state);
      const { manifest, policies, developmentsByStage, settings } = action.payload;
      const policyDeck = policies.map((policy) => policy.id);
      const deckOrder = Object.values(developmentsByStage).flat().map((dev) => dev.id);
      return {
        ...state,
        manifest,
        policies,
        developmentsByStage,
        policyDeck,
        deckOrder,
        settings,
        history: [...state.history, snapshot],
        future: [],
      };
    }
    case "DEAL_STAGE": {
      const snapshot = createSnapshot(state);
      const currentStageCards = state.developmentsByStage[state.stageIndex] || [];
      const { faceUp, faceDown, remaining } = dealDevelopments(
        currentStageCards,
        state.settings.devFaceupStart,
        state.settings.devFacedownStart,
      );
      return {
        ...state,
        faceUp,
        faceDown,
        dormant: currentStageCards.filter((card) => card.activation.type === "conditional"),
        round: 1,
        history: [...state.history, snapshot],
        future: [],
        log: [...state.log, `Dealt stage ${state.stageIndex} developments.`],
      };
    }
    case "DRAW_ROUND": {
      const snapshot = createSnapshot(state);
      const currentStageCards = state.developmentsByStage[state.stageIndex] || [];
      const remaining = currentStageCards.filter(
        (card) => !state.faceUp.some((up) => up.id === card.id) && !state.faceDown.some((down) => down.id === card.id),
      );
      const { faceUp, faceDown } = dealDevelopments(
        remaining,
        state.settings.devFaceupPerRound,
        state.settings.devFacedownPerRound,
      );
      const { drawnPolicies, remainingPolicies } = drawPolicies(state.policies, state.policyDeck, state.settings.policyDrawPerRound);
      return {
        ...state,
        faceUp: [...state.faceUp, ...faceUp],
        faceDown: [...state.faceDown, ...faceDown],
        policyDeck: remainingPolicies,
        hand: [...state.hand, ...drawnPolicies],
        round: state.round + 1,
        history: [...state.history, snapshot],
        future: [],
        log: [...state.log, `Round ${state.round + 1} draw.`],
      };
    }
    case "PLAY_POLICY": {
      const snapshot = createSnapshot(state);
      const policy = state.hand.find((item) => item.id === action.payload.policyId);
      if (!policy) return state;
      if (state.implemented.length >= state.settings.maxPoliciesPerRound) return state;
      return {
        ...state,
        implemented: [...state.implemented, policy],
        hand: state.hand.filter((item) => item.id !== action.payload.policyId),
        attachments: { ...state.attachments, [policy.id]: state.attachments[policy.id] || [] },
        history: [...state.history, snapshot],
        future: [],
        log: [...state.log, `Implemented ${policy.title}.`],
      };
    }
    case "ATTACH_DEV": {
      const snapshot = createSnapshot(state);
      const dev = findDev(state, action.payload.devId);
      if (!dev) return state;
      const attachments = { ...state.attachments };
      attachments[action.payload.policyId] = [...(attachments[action.payload.policyId] || []), dev];
      return {
        ...state,
        faceUp: state.faceUp.filter((item) => item.id !== dev.id),
        faceDown: state.faceDown.filter((item) => item.id !== dev.id),
        dormant: state.dormant.filter((item) => item.id !== dev.id),
        attachments,
        history: [...state.history, snapshot],
        future: [],
        log: [...state.log, `Attached ${dev.title} under policy.`],
      };
    }
    case "AUTO_ATTACH": {
      const snapshot = createSnapshot(state);
      const implementedTags = new Set(state.implemented.flatMap((policy) => policy.tags));
      const autoTargets = state.faceUp.filter(
        (dev) => dev.activation.type === "conditional" && dev.activation.required_policy_tags.every((tag) => implementedTags.has(tag)),
      );
      const attachments = { ...state.attachments };
      autoTargets.forEach((dev) => {
        const policy = state.implemented.find((p) => p.tags.some((tag) => dev.activation.required_policy_tags.includes(tag)));
        if (policy) {
          attachments[policy.id] = [...(attachments[policy.id] || []), dev];
        }
      });
      return {
        ...state,
        faceUp: state.faceUp.filter((dev) => !autoTargets.some((target) => target.id === dev.id)),
        attachments,
        history: [...state.history, snapshot],
        future: [],
        log: [...state.log, `Auto-attached ${autoTargets.length} developments.`],
      };
    }
    case "SELECT_DEV":
      return { ...state, selectedDevId: action.payload.devId };
    case "SELECT_POLICY":
      return { ...state, selectedPolicyId: action.payload.policyId };
    case "ADVANCE_STAGE": {
      const snapshot = createSnapshot(state);
      return {
        ...state,
        stageIndex: Math.min(state.stageIndex + 1, Object.keys(state.developmentsByStage).length - 1),
        faceUp: [],
        faceDown: [],
        dormant: [],
        implemented: [],
        attachments: {},
        round: 0,
        history: [...state.history, snapshot],
        future: [],
        log: [...state.log, `Advanced to stage ${state.stageIndex + 1}.`],
      };
    }
    case "UNDO": {
      if (state.history.length === 0) return state;
      const previous = state.history[state.history.length - 1];
      const history = state.history.slice(0, -1);
      return { ...previous, history, future: [createSnapshot(state), ...state.future] };
    }
    case "REDO": {
      if (state.future.length === 0) return state;
      const next = state.future[0];
      const future = state.future.slice(1);
      return { ...next, history: [...state.history, createSnapshot(state)], future };
    }
    default:
      return state;
  }
}

function dealDevelopments(cards: DevelopmentCard[], faceUpCount: number, faceDownCount: number) {
  const remaining = [...cards];
  const faceUp = remaining.splice(0, faceUpCount);
  const faceDown = remaining.splice(0, faceDownCount);
  return { faceUp, faceDown, remaining };
}

function drawPolicies(policies: PolicyCard[], deck: string[], count: number) {
  const remaining = [...deck];
  const drawn = remaining.splice(0, count);
  return {
    drawnPolicies: policies.filter((policy) => drawn.includes(policy.id)),
    remainingPolicies: remaining,
  };
}

function findDev(state: GameState, devId: string): DevelopmentCard | undefined {
  return (
    state.faceUp.find((item) => item.id === devId) ||
    state.faceDown.find((item) => item.id === devId) ||
    state.dormant.find((item) => item.id === devId)
  );
}

function createSnapshot(state: GameState): GameStateSnapshot {
  const { history, future, ...snapshot } = state;
  return snapshot;
}
