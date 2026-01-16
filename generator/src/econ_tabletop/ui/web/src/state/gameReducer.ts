import { DevelopmentCard, Effect, GameSettings, GameState, GameStateSnapshot, PolicyCard, RoundModifiers } from "./types";

export type Action =
  | { type: "INIT_DECK"; payload: { manifest: Record<string, unknown>; policies: PolicyCard[]; developmentsByStage: Record<number, DevelopmentCard[]>; settings: GameSettings } }
  | { type: "DEAL_STAGE" }
  | { type: "DRAW_ROUND" }
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
    deckOrder: [],
    policyDeck: [],
    faceUp: [],
    faceDown: [],
    dormant: [],
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
        roundModifiers: defaultRoundModifiers(),
        triggeredDevEffects: [],
        history: [...state.history, snapshot],
        future: [],
      };
    }
    case "DEAL_STAGE": {
      const snapshot = createSnapshot(state);
      const currentStageCards = state.developmentsByStage[state.stageIndex] || [];
      const { faceUp, faceDown } = dealDevelopments(
        currentStageCards,
        state.settings.devFaceupStart,
        state.settings.devFacedownStart,
      );
      let nextState: GameState = {
        ...state,
        faceUp,
        faceDown,
        dormant: currentStageCards.filter((card) => card.activation.type === "conditional"),
        round: 1,
        roundModifiers: defaultRoundModifiers(),
        history: [...state.history, snapshot],
        future: [],
        log: [...state.log, `Dealt stage ${state.stageIndex} developments.`],
      };
      nextState = applyEffectsForDevelopments(nextState, faceUp);
      return nextState;
    }
    case "DRAW_ROUND": {
      const snapshot = createSnapshot(state);
      const currentStageCards = state.developmentsByStage[state.stageIndex] || [];
      const remaining = currentStageCards.filter(
        (card) => !state.faceUp.some((up) => up.id === card.id) && !state.faceDown.some((down) => down.id === card.id),
      );
      const faceUpCount = Math.max(0, state.settings.devFaceupPerRound + state.roundModifiers.devDrawDeltaNext);
      const { faceUp, faceDown } = dealDevelopments(
        remaining,
        faceUpCount,
        state.settings.devFacedownPerRound,
      );
      const policyDrawCount = Math.max(0, state.settings.policyDrawPerRound + state.roundModifiers.policyDrawDeltaNext);
      const { drawnPolicies, remainingPolicies } = drawPolicies(state.policies, state.policyDeck, policyDrawCount);
      let nextState: GameState = {
        ...state,
        faceUp: [...state.faceUp, ...faceUp],
        faceDown: [...state.faceDown, ...faceDown],
        policyDeck: remainingPolicies,
        hand: [...state.hand, ...drawnPolicies],
        round: state.round + 1,
        roundModifiers: defaultRoundModifiers(),
        history: [...state.history, snapshot],
        future: [],
        log: [...state.log, `Round ${state.round + 1} draw.`],
      };
      nextState = applyEffectsForDevelopments(nextState, faceUp);
      return nextState;
    }
    case "DEAL_DEVELOPMENTS": {
      const snapshot = createSnapshot(state);
      const stageIndex = Math.max(0, action.payload.stageIndex);
      const stageCards = state.developmentsByStage[stageIndex] || [];
      const faceUpCount = Math.max(0, action.payload.faceUpCount);
      const faceDownCount = Math.max(0, action.payload.faceDownCount);
      const { faceUp, faceDown } = dealDevelopments(stageCards, faceUpCount, faceDownCount);
      let nextState: GameState = {
        ...state,
        faceUp: [...state.faceUp, ...faceUp],
        faceDown: [...state.faceDown, ...faceDown],
        dormant: stageCards.filter((card) => card.activation.type === "conditional"),
        round: state.round + 1,
        history: [...state.history, snapshot],
        future: [],
        log: [...state.log, `Dealt ${faceUp.length + faceDown.length} developments from stage ${stageIndex}.`],
      };
      nextState = applyEffectsForDevelopments(nextState, faceUp);
      return nextState;
    }
    case "DRAW_POLICIES": {
      const snapshot = createSnapshot(state);
      const count = Math.max(0, action.payload.count);
      if (count === 0) return state;
      const { drawnPolicies, remainingPolicies } = drawPolicies(state.policies, state.policyDeck, count);
      return {
        ...state,
        policyDeck: remainingPolicies,
        hand: [...state.hand, ...drawnPolicies],
        round: state.round + 1,
        history: [...state.history, snapshot],
        future: [],
        log: [...state.log, `Drew ${drawnPolicies.length} policy card(s).`],
      };
    }
    case "PLAY_POLICY": {
      const snapshot = createSnapshot(state);
      const policy = state.hand.find((item) => item.id === action.payload.policyId);
      if (!policy) return state;
      const maxPolicies = Math.max(0, state.settings.maxPoliciesPerRound + state.roundModifiers.maxPoliciesDeltaThisRound);
      if (state.implemented.length >= maxPolicies) return state;
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
      let nextState: GameState = {
        ...state,
        faceUp: state.faceUp.filter((item) => item.id !== dev.id),
        faceDown: state.faceDown.filter((item) => item.id !== dev.id),
        dormant: state.dormant.filter((item) => item.id !== dev.id),
        attachments,
        history: [...state.history, snapshot],
        future: [],
        log: [...state.log, `Attached ${dev.title} under policy.`],
      };
      nextState = applyEffectsForDevelopments(nextState, [dev]);
      return nextState;
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
      let nextState: GameState = {
        ...state,
        faceUp: state.faceUp.filter((dev) => !autoTargets.some((target) => target.id === dev.id)),
        attachments,
        history: [...state.history, snapshot],
        future: [],
        log: [...state.log, `Auto-attached ${autoTargets.length} developments.`],
      };
      nextState = applyEffectsForDevelopments(nextState, autoTargets);
      return nextState;
    }
    case "DISCARD_CARD": {
      const snapshot = createSnapshot(state);
      if (action.payload.kind === "policy") {
        const policy = state.policies.find((item) => item.id === action.payload.id);
        if (!policy) return state;
        const discardedPolicies = [...state.discardedPolicies, policy];
        const attached = state.attachments[action.payload.id] || [];
        const attachments = { ...state.attachments };
        delete attachments[action.payload.id];
        const remainingHand = state.hand.filter((item) => item.id !== action.payload.id);
        const remainingImplemented = state.implemented.filter((item) => item.id !== action.payload.id);
        const nextState: GameState = {
          ...state,
          hand: remainingHand,
          implemented: remainingImplemented,
          attachments,
          discardedPolicies,
          discardedDevelopments: [...state.discardedDevelopments, ...attached],
          selectedPolicyId: state.selectedPolicyId === action.payload.id ? null : state.selectedPolicyId,
          history: [...state.history, snapshot],
          future: [],
          log: [...state.log, `Discarded policy ${policy.title}.`],
        };
        return nextState;
      }
      const dev = findDev(state, action.payload.id);
      if (!dev) return state;
      const { attachments, removed } = removeDevFromAttachments(state.attachments, action.payload.id);
      const discardSet = new Map<string, DevelopmentCard>();
      [dev, ...removed].forEach((card) => discardSet.set(card.id, card));
      return {
        ...state,
        faceUp: state.faceUp.filter((item) => item.id !== action.payload.id),
        faceDown: state.faceDown.filter((item) => item.id !== action.payload.id),
        dormant: state.dormant.filter((item) => item.id !== action.payload.id),
        attachments,
        discardedDevelopments: [...state.discardedDevelopments, ...discardSet.values()],
        selectedDevId: state.selectedDevId === action.payload.id ? null : state.selectedDevId,
        history: [...state.history, snapshot],
        future: [],
        log: [...state.log, `Discarded development ${dev.title}.`],
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
        discardedDevelopments: [],
        discardedPolicies: [],
        round: 0,
        roundModifiers: defaultRoundModifiers(),
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
    state.dormant.find((item) => item.id === devId) ||
    Object.values(state.attachments)
      .flat()
      .find((item) => item.id === devId)
  );
}

function removeDevFromAttachments(attachments: Record<string, DevelopmentCard[]>, devId: string) {
  const updated: Record<string, DevelopmentCard[]> = {};
  const removed: DevelopmentCard[] = [];
  Object.entries(attachments).forEach(([policyId, devs]) => {
    const remaining = devs.filter((dev) => dev.id !== devId);
    if (remaining.length !== devs.length) {
      removed.push(...devs.filter((dev) => dev.id === devId));
    }
    if (remaining.length > 0) {
      updated[policyId] = remaining;
    }
  });
  return { attachments: updated, removed };
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
      const { nextState, drawn } = drawDevelopmentsFromStage(state, state.stageIndex + stageOffset, count, source);
      return applyEffectsForDevelopments(nextState, drawn);
    }
    case "DRAW_DEV_NEXT_STAGE_NOW": {
      const count = readParam(effect.params, "count");
      if (count <= 0) return state;
      const { nextState, drawn } = drawDevelopmentsFromStage(state, state.stageIndex + 1, count, source);
      return applyEffectsForDevelopments(nextState, drawn);
    }
    case "MODIFY_DEV_DRAW_NEXT_ROUND": {
      const delta = readParam(effect.params, "delta");
      const roundModifiers = {
        ...state.roundModifiers,
        devDrawDeltaNext: state.roundModifiers.devDrawDeltaNext + delta,
      };
      return {
        ...state,
        roundModifiers,
        log: [...state.log, `${source.title} will ${delta >= 0 ? "increase" : "decrease"} next round's development draw by ${Math.abs(delta)}.`],
      };
    }
    case "MODIFY_POLICY_DRAW_NEXT_ROUND": {
      const delta = readParam(effect.params, "delta");
      const roundModifiers = {
        ...state.roundModifiers,
        policyDrawDeltaNext: state.roundModifiers.policyDrawDeltaNext + delta,
      };
      return {
        ...state,
        roundModifiers,
        log: [...state.log, `${source.title} will ${delta >= 0 ? "increase" : "decrease"} next round's policy draw by ${Math.abs(delta)}.`],
      };
    }
    case "MODIFY_MAX_POLICIES_THIS_ROUND": {
      const delta = readParam(effect.params, "delta");
      const roundModifiers = {
        ...state.roundModifiers,
        maxPoliciesDeltaThisRound: state.roundModifiers.maxPoliciesDeltaThisRound + delta,
      };
      return {
        ...state,
        roundModifiers,
        log: [...state.log, `${source.title} changes max policies this round by ${delta >= 0 ? "+" : ""}${delta}.`],
      };
    }
    default:
      return state;
  }
}

function drawDevelopmentsFromStage(
  state: GameState,
  stageIndex: number,
  count: number,
  source: DevelopmentCard,
): { nextState: GameState; drawn: DevelopmentCard[] } {
  const stageCards = state.developmentsByStage[stageIndex] || [];
  const usedIds = new Set([
    ...state.faceUp.map((card) => card.id),
    ...state.faceDown.map((card) => card.id),
    ...state.dormant.map((card) => card.id),
    ...Object.values(state.attachments).flat().map((card) => card.id),
  ]);
  const available = stageCards.filter((card) => !usedIds.has(card.id));
  const drawn = available.slice(0, count);
  if (drawn.length === 0) return { nextState: state, drawn: [] };
  const drawnIds = new Set(drawn.map((card) => card.id));
  const updatedStage = stageCards.filter((card) => !drawnIds.has(card.id));
  const nextState = {
    ...state,
    developmentsByStage: { ...state.developmentsByStage, [stageIndex]: updatedStage },
    faceUp: [...state.faceUp, ...drawn],
    log: [...state.log, `${source.title} draws ${drawn.length} development card(s) from stage ${stageIndex}.`],
  };
  return { nextState, drawn };
}

function readParam(params: Record<string, number>, key: string): number {
  const value = params[key];
  if (typeof value === "number" && !Number.isNaN(value)) return value;
  return 0;
}
