import { DevelopmentCard, Effect, GameSettings, GameState, GameStateSnapshot, PolicyCard, RoundModifiers } from "./types";

export type Action =
  | { type: "HYDRATE"; payload: GameState }
  | {
      type: "INIT_DECK";
      payload: {
        manifest: Record<string, unknown>;
        policies: PolicyCard[];
        developmentsByStage: Record<number, DevelopmentCard[]>;
        settings: GameSettings;
      };
    }
  | { type: "START_GAME" }
  | { type: "DEAL_DEVELOPMENTS"; payload: { stageIndex: number; faceUpCount: number; faceDownCount: number } }
  | { type: "DRAW_POLICIES"; payload: { count: number } }
  | { type: "PLAY_POLICY"; payload: { policyId: string } }
  | { type: "ATTACH_DEV"; payload: { policyId: string; devId: string } }
  | { type: "AUTO_ATTACH" }
  | { type: "DISCARD_CARD"; payload: { kind: "policy" | "development"; id: string } }
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
    developmentDrawIndexByStage: {},
    deckOrder: [],
    policyDeck: [],
    faceUp: [],
    faceDown: [],
    implemented: [],
    hand: [],
    attachments: {},
    discardedDevelopments: [],
    discardedPolicies: [],
    log: [],
    selectedDevId: null,
    selectedPolicyId: null,
    roundModifiers: defaultRoundModifiers(),
    triggeredDevEffects: [],
    budgetSpentThisStage: 0,
    policiesPlayedThisStage: [],
    history: [],
    future: [],
    settings,
  };
}

export function gameReducer(state: GameState, action: Action): GameState {
  switch (action.type) {
    case "HYDRATE":
      return {
        ...createInitialState(action.payload.settings),
        ...action.payload,
        developmentDrawIndexByStage:
          action.payload.developmentDrawIndexByStage || initStageDrawIndex(action.payload.developmentsByStage),
        budgetSpentThisStage: action.payload.budgetSpentThisStage || 0,
        policiesPlayedThisStage: action.payload.policiesPlayedThisStage || [],
        history: [],
        future: [],
      };
    case "INIT_DECK": {
      const snapshot = createSnapshot(state);
      const { manifest, policies, developmentsByStage, settings } = action.payload;
      return {
        ...createInitialState(settings),
        manifest,
        policies,
        developmentsByStage,
        developmentDrawIndexByStage: initStageDrawIndex(developmentsByStage),
        deckOrder: Object.values(developmentsByStage).flat().map((dev) => dev.id),
        policyDeck: policies.map((policy) => policy.id),
        history: [...state.history, snapshot],
      };
    }
    case "START_GAME": {
      if (!state.manifest || state.round > 0) return state;
      const snapshot = createSnapshot(state);
      let nextState = withHistory(state, snapshot);
      const policyResult = drawPoliciesFromDeck(nextState, nextState.settings.handSize);
      nextState = {
        ...policyResult.nextState,
        hand: [...policyResult.nextState.hand, ...policyResult.drawnPolicies],
        round: 1,
        log: [...policyResult.nextState.log, `Started game with ${policyResult.drawnPolicies.length} policy cards and stage 1 developments.`],
      };
      const stageDeal = drawDevelopmentPacket(
        nextState,
        nextState.stageIndex,
        nextState.settings.devFaceupStart,
        nextState.settings.devFacedownStart,
      );
      nextState = {
        ...stageDeal.nextState,
        faceUp: [...nextState.faceUp, ...stageDeal.faceUp],
        faceDown: [...nextState.faceDown, ...stageDeal.faceDown],
      };
      return applyEffectsForDevelopments(nextState, stageDeal.faceUp);
    }
    case "DEAL_DEVELOPMENTS": {
      const snapshot = createSnapshot(state);
      const stageIndex = Math.max(0, action.payload.stageIndex);
      const faceUpCount = Math.max(0, action.payload.faceUpCount);
      const faceDownCount = Math.max(0, action.payload.faceDownCount);
      const stageDeal = drawDevelopmentPacket(withHistory(state, snapshot), stageIndex, faceUpCount, faceDownCount);
      let nextState: GameState = {
        ...stageDeal.nextState,
        faceUp: [...stageDeal.nextState.faceUp, ...stageDeal.faceUp],
        faceDown: [...stageDeal.nextState.faceDown, ...stageDeal.faceDown],
        log: [
          ...stageDeal.nextState.log,
          `Dealt ${stageDeal.faceUp.length + stageDeal.faceDown.length} developments from stage ${stageIndex + 1}.`,
        ],
      };
      nextState = applyEffectsForDevelopments(nextState, stageDeal.faceUp);
      return nextState;
    }
    case "DRAW_POLICIES": {
      const snapshot = createSnapshot(state);
      const count = Math.max(0, action.payload.count);
      if (count === 0) return state;
      const policyResult = drawPoliciesFromDeck(withHistory(state, snapshot), count);
      return {
        ...policyResult.nextState,
        hand: [...policyResult.nextState.hand, ...policyResult.drawnPolicies],
        log: [...policyResult.nextState.log, `Drew ${policyResult.drawnPolicies.length} policy card(s).`],
      };
    }
    case "PLAY_POLICY": {
      const snapshot = createSnapshot(state);
      const policy = state.hand.find((item) => item.id === action.payload.policyId);
      if (!policy) return state;
      const maxPolicies = Math.max(0, state.settings.maxPoliciesPerRound + state.roundModifiers.maxPoliciesDeltaThisRound);
      if (state.policiesPlayedThisStage.length >= maxPolicies) return state;
      const budgetCost = getPolicyBudgetCost(policy);
      if (state.budgetSpentThisStage + budgetCost > state.settings.budgetPerStage) return state;
      return {
        ...withHistory(state, snapshot),
        implemented: state.implemented.some((item) => item.id === policy.id) ? state.implemented : [...state.implemented, policy],
        hand: state.hand.filter((item) => item.id !== action.payload.policyId),
        attachments: { ...state.attachments, [policy.id]: state.attachments[policy.id] || [] },
        budgetSpentThisStage: state.budgetSpentThisStage + budgetCost,
        policiesPlayedThisStage: [...state.policiesPlayedThisStage, policy.id],
        log: [
          ...state.log,
          `Implemented ${policy.title} for $${budgetCost}. ${Math.max(0, state.settings.budgetPerStage - state.budgetSpentThisStage - budgetCost)} budget left this stage.`,
        ],
      };
    }
    case "ATTACH_DEV": {
      const snapshot = createSnapshot(state);
      const dev = findDev(state, action.payload.devId);
      if (!dev) return state;
      const attachments = { ...state.attachments };
      const alreadyAttached = (attachments[action.payload.policyId] || []).some((item) => item.id === dev.id);
      if (alreadyAttached) return state;
      attachments[action.payload.policyId] = [...(attachments[action.payload.policyId] || []), dev];
      const nextState = removeDevelopmentFromBoard(withHistory(state, snapshot), dev.id);
      return applyEffectsForDevelopments(
        {
          ...nextState,
          attachments,
          log: [...nextState.log, `Attached ${dev.title} to a policy.`],
        },
        [dev],
      );
    }
    case "AUTO_ATTACH": {
      const snapshot = createSnapshot(state);
      const implementedTags = new Set(state.implemented.flatMap((policy) => policy.tags));
      const autoTargets = state.faceUp.filter(
        (dev) =>
          dev.activation.type === "conditional" &&
          dev.activation.required_policy_tags.length > 0 &&
          dev.activation.required_policy_tags.every((tag) => implementedTags.has(tag)),
      );
      if (autoTargets.length === 0) {
        return {
          ...withHistory(state, snapshot),
          log: [...state.log, "No conditional developments matched current policies."],
        };
      }
      let nextState = withHistory(state, snapshot);
      const attachments = { ...state.attachments };
      autoTargets.forEach((dev) => {
        const policy = state.implemented.find((item) =>
          item.tags.some((tag) => dev.activation.required_policy_tags.includes(tag)),
        );
        if (!policy) return;
        attachments[policy.id] = [...(attachments[policy.id] || []), dev];
        nextState = removeDevelopmentFromBoard(nextState, dev.id);
      });
      nextState = {
        ...nextState,
        attachments,
        log: [...nextState.log, `Auto-attached ${autoTargets.length} development card(s).`],
      };
      return applyEffectsForDevelopments(nextState, autoTargets);
    }
    case "DISCARD_CARD": {
      const snapshot = createSnapshot(state);
      if (action.payload.kind === "policy") {
        const policy = state.policies.find((item) => item.id === action.payload.id);
        if (!policy) return state;
        const attached = state.attachments[action.payload.id] || [];
        const attachments = { ...state.attachments };
        delete attachments[action.payload.id];
        return {
          ...withHistory(state, snapshot),
          hand: state.hand.filter((item) => item.id !== action.payload.id),
          implemented: state.implemented.filter((item) => item.id !== action.payload.id),
          attachments,
          discardedPolicies: [...state.discardedPolicies, policy],
          discardedDevelopments: [...state.discardedDevelopments, ...attached],
          selectedPolicyId: state.selectedPolicyId === action.payload.id ? null : state.selectedPolicyId,
          log: [...state.log, `Discarded policy ${policy.title}.`],
        };
      }
      const dev = findDev(state, action.payload.id);
      if (!dev) return state;
      const nextState = removeDevelopmentFromBoard(withHistory(state, snapshot), action.payload.id);
      return {
        ...nextState,
        discardedDevelopments: [...nextState.discardedDevelopments, dev],
        selectedDevId: nextState.selectedDevId === action.payload.id ? null : nextState.selectedDevId,
        log: [...nextState.log, `Discarded development ${dev.title}.`],
      };
    }
    case "SELECT_DEV":
      return { ...state, selectedDevId: action.payload.devId };
    case "SELECT_POLICY":
      return { ...state, selectedPolicyId: action.payload.policyId };
    case "ADVANCE_STAGE": {
      const maxStageIndex = Math.max(0, Object.keys(state.developmentsByStage).length - 1);
      if (state.stageIndex >= maxStageIndex) return state;
      const snapshot = createSnapshot(state);
      const nextStageIndex = Math.min(state.stageIndex + 1, maxStageIndex);
      const flipped = state.faceDown;
      let nextState = withHistory(state, snapshot);
      nextState = {
        ...nextState,
        stageIndex: nextStageIndex,
        round: state.round + 1,
        faceUp: [...state.faceUp, ...flipped],
        faceDown: [],
        roundModifiers: defaultRoundModifiers(),
        budgetSpentThisStage: 0,
        policiesPlayedThisStage: [],
      };
      const policyResult = drawPoliciesFromDeck(nextState, Math.max(0, nextState.settings.policyDrawPerRound + nextState.roundModifiers.policyDrawDeltaNext));
      nextState = {
        ...policyResult.nextState,
        hand: [...policyResult.nextState.hand, ...policyResult.drawnPolicies],
      };
      const stageDeal = drawDevelopmentPacket(
        nextState,
        nextStageIndex,
        nextState.settings.devFaceupStart,
        nextState.settings.devFacedownStart,
      );
      nextState = {
        ...stageDeal.nextState,
        faceUp: [...stageDeal.nextState.faceUp, ...stageDeal.faceUp],
        faceDown: [...stageDeal.nextState.faceDown, ...stageDeal.faceDown],
        log: [
          ...stageDeal.nextState.log,
          `Advanced to stage ${nextStageIndex + 1}. Flipped ${flipped.length} face-down card(s), drew ${policyResult.drawnPolicies.length} policies, and dealt ${stageDeal.faceUp.length + stageDeal.faceDown.length} new developments.`,
        ],
      };
      return applyEffectsForDevelopments(nextState, [...flipped, ...stageDeal.faceUp]);
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

function initStageDrawIndex(developmentsByStage: Record<number, DevelopmentCard[]>) {
  return Object.keys(developmentsByStage).reduce<Record<number, number>>((acc, key) => {
    acc[Number(key)] = 0;
    return acc;
  }, {});
}

function withHistory(state: GameState, snapshot: GameStateSnapshot): GameState {
  return {
    ...state,
    history: [...state.history, snapshot],
    future: [],
  };
}

function drawPoliciesFromDeck(state: GameState, count: number) {
  const remaining = [...state.policyDeck];
  const drawnIds = remaining.splice(0, Math.max(0, count));
  return {
    nextState: { ...state, policyDeck: remaining },
    drawnPolicies: state.policies.filter((policy) => drawnIds.includes(policy.id)),
  };
}

function drawDevelopmentPacket(state: GameState, stageIndex: number, faceUpCount: number, faceDownCount: number) {
  const stageCards = state.developmentsByStage[stageIndex] || [];
  const currentIndex = state.developmentDrawIndexByStage[stageIndex] || 0;
  const faceUp = stageCards.slice(currentIndex, currentIndex + faceUpCount);
  const faceDown = stageCards.slice(currentIndex + faceUpCount, currentIndex + faceUpCount + faceDownCount);
  const nextIndex = currentIndex + faceUp.length + faceDown.length;
  return {
    nextState: {
      ...state,
      developmentDrawIndexByStage: { ...state.developmentDrawIndexByStage, [stageIndex]: nextIndex },
    },
    faceUp,
    faceDown,
  };
}

function findDev(state: GameState, devId: string): DevelopmentCard | undefined {
  return (
    state.faceUp.find((item) => item.id === devId) ||
    state.faceDown.find((item) => item.id === devId) ||
    Object.values(state.attachments)
      .flat()
      .find((item) => item.id === devId)
  );
}

function removeDevelopmentFromBoard(state: GameState, devId: string): GameState {
  const attachments: Record<string, DevelopmentCard[]> = {};
  Object.entries(state.attachments).forEach(([policyId, devs]) => {
    const remaining = devs.filter((item) => item.id !== devId);
    if (remaining.length > 0) {
      attachments[policyId] = remaining;
    }
  });
  return {
    ...state,
    faceUp: state.faceUp.filter((item) => item.id !== devId),
    faceDown: state.faceDown.filter((item) => item.id !== devId),
    attachments,
  };
}

function createSnapshot(state: GameState): GameStateSnapshot {
  const { history, future, ...snapshot } = state;
  return snapshot;
}

function defaultRoundModifiers(): RoundModifiers {
  return {
    devDrawDeltaNext: 0,
    policyDrawDeltaNext: 0,
    maxPoliciesDeltaThisRound: 0,
  };
}

function getPolicyBudgetCost(policy: PolicyCard): number {
  const raw = policy.cost?.budget_cost ?? policy.cost?.budget_level ?? 2;
  const parsed = Number(raw);
  if (!Number.isFinite(parsed)) return 2;
  return Math.max(1, Math.min(4, parsed));
}

function applyEffectsForDevelopments(state: GameState, developments: DevelopmentCard[]): GameState {
  let nextState = { ...state };
  developments.forEach((dev) => {
    if (nextState.triggeredDevEffects.includes(dev.id)) return;
    if (!dev.effects || dev.effects.length === 0) return;
    dev.effects.forEach((effect) => {
      nextState = applyEffect(nextState, effect, dev);
    });
    nextState = {
      ...nextState,
      triggeredDevEffects: [...nextState.triggeredDevEffects, dev.id],
    };
  });
  return nextState;
}

function applyEffect(state: GameState, effect: Effect, source: DevelopmentCard): GameState {
  switch (effect.type) {
    case "DRAW_DEV_NOW": {
      const count = readParam(effect.params, "count");
      const stageOffset = readParam(effect.params, "stage_offset");
      if (count <= 0) return state;
      const { nextState, drawn } = drawFaceUpFromStage(state, state.stageIndex + stageOffset, count, source);
      return applyEffectsForDevelopments(nextState, drawn);
    }
    case "DRAW_DEV_NEXT_STAGE_NOW": {
      const count = readParam(effect.params, "count");
      if (count <= 0) return state;
      const { nextState, drawn } = drawFaceUpFromStage(state, state.stageIndex + 1, count, source);
      return applyEffectsForDevelopments(nextState, drawn);
    }
    case "MODIFY_DEV_DRAW_NEXT_ROUND": {
      const delta = readParam(effect.params, "delta");
      return {
        ...state,
        roundModifiers: {
          ...state.roundModifiers,
          devDrawDeltaNext: state.roundModifiers.devDrawDeltaNext + delta,
        },
        log: [
          ...state.log,
          `${source.title} will ${delta >= 0 ? "increase" : "decrease"} the next stage's extra development draw by ${Math.abs(delta)}.`,
        ],
      };
    }
    case "MODIFY_POLICY_DRAW_NEXT_ROUND": {
      const delta = readParam(effect.params, "delta");
      return {
        ...state,
        roundModifiers: {
          ...state.roundModifiers,
          policyDrawDeltaNext: state.roundModifiers.policyDrawDeltaNext + delta,
        },
        log: [
          ...state.log,
          `${source.title} will ${delta >= 0 ? "increase" : "decrease"} the next stage's policy draw by ${Math.abs(delta)}.`,
        ],
      };
    }
    case "MODIFY_MAX_POLICIES_THIS_ROUND": {
      const delta = readParam(effect.params, "delta");
      return {
        ...state,
        roundModifiers: {
          ...state.roundModifiers,
          maxPoliciesDeltaThisRound: state.roundModifiers.maxPoliciesDeltaThisRound + delta,
        },
        log: [...state.log, `${source.title} changes this stage's policy limit by ${delta >= 0 ? "+" : ""}${delta}.`],
      };
    }
    default:
      return state;
  }
}

function drawFaceUpFromStage(
  state: GameState,
  stageIndex: number,
  count: number,
  source: DevelopmentCard,
): { nextState: GameState; drawn: DevelopmentCard[] } {
  const stageDeal = drawDevelopmentPacket(state, stageIndex, count, 0);
  if (stageDeal.faceUp.length === 0) return { nextState: state, drawn: [] };
  const nextState = {
    ...stageDeal.nextState,
    faceUp: [...stageDeal.nextState.faceUp, ...stageDeal.faceUp],
    log: [...stageDeal.nextState.log, `${source.title} reveals ${stageDeal.faceUp.length} more development card(s).`],
  };
  return { nextState, drawn: stageDeal.faceUp };
}

function readParam(params: Record<string, number>, key: string): number {
  const value = params[key];
  if (typeof value === "number" && !Number.isNaN(value)) return value;
  return 0;
}
