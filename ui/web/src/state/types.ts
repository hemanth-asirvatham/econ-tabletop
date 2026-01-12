export type PolicyCard = {
  id: string;
  title: string;
  short_description: string;
  description: string;
  category: string;
  cost: {
    budget_level: number;
    implementation_complexity: number;
    notes: string;
  };
  timeline: {
    time_to_launch: string;
    time_to_impact: string;
  };
  impact_score: number;
  tags: string[];
  addresses_tags: string[];
  side_effect_tags: string[];
  prerequisites_policy_tags: string[];
  synergy_policy_tags: string[];
  role_restrictions: string[];
  art_prompt: string;
  flavor_quote?: string;
};

export type DevelopmentCard = {
  id: string;
  stage: number;
  title: string;
  short_description: string;
  description: string;
  valence: "positive" | "negative" | "mixed";
  arrows_up: number;
  arrows_down: number;
  severity: number;
  tags: string[];
  thread_id: string;
  supersedes: string | null;
  activation: {
    type: "immediate" | "conditional";
    required_policy_tags: string[];
  };
  effects: Effect[];
  art_prompt: string;
  suggested_visibility?: "faceup" | "facedown" | "either";
};

export type Effect = {
  type:
    | "DRAW_DEV_NOW"
    | "DRAW_DEV_NEXT_STAGE_NOW"
    | "MODIFY_DEV_DRAW_NEXT_ROUND"
    | "MODIFY_POLICY_DRAW_NEXT_ROUND"
    | "MODIFY_MAX_POLICIES_THIS_ROUND";
  params: Record<string, number>;
};

export type GameState = {
  manifest: Record<string, unknown> | null;
  stageIndex: number;
  round: number;
  policies: PolicyCard[];
  developmentsByStage: Record<number, DevelopmentCard[]>;
  deckOrder: string[];
  policyDeck: string[];
  faceUp: DevelopmentCard[];
  faceDown: DevelopmentCard[];
  dormant: DevelopmentCard[];
  implemented: PolicyCard[];
  hand: PolicyCard[];
  attachments: Record<string, DevelopmentCard[]>;
  log: string[];
  selectedDevId: string | null;
  selectedPolicyId: string | null;
  history: GameStateSnapshot[];
  future: GameStateSnapshot[];
  settings: GameSettings;
};

export type GameSettings = {
  players: number;
  handSize: number;
  devFaceupStart: number;
  devFacedownStart: number;
  devFaceupPerRound: number;
  devFacedownPerRound: number;
  policyDrawPerRound: number;
  maxPoliciesPerRound: number;
};

export type GameStateSnapshot = Omit<GameState, "history" | "future">;
