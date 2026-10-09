import { request } from "./http";
import { setSession } from "./session";

export type HealthStatus = {
  status: string;
  version: string;
};

export type SessionResponse = {
  account_id: string;
  session_token: string;
  expires_at: string;
};

export type PrivacyView = {
  version: number;
  discoverable: boolean;
  show_distance: boolean;
  allow_ai_matching: boolean;
  allow_product_analytics: boolean;
  consents: Array<{
    consent_id: string;
    purpose: string;
    policy_version: string;
    decision: string;
    occurred_at: string;
  }>;
};

export type CodeLabel = { code: string; label: string };

export type FactKeyMeta = CodeLabel & {
  purpose: string;
  kind: "repeatable" | "ordinal";
  allowed?: string[];
};

export type PromptMeta = CodeLabel & { side: "self" | "desired_partner" };

export type OnboardingMetadata = {
  flow_version: string;
  policy_version: string;
  genders: CodeLabel[];
  orientations: CodeLabel[];
  search_modes: CodeLabel[];
  relationship_goals: CodeLabel[];
  cities: CodeLabel[];
  public_areas: CodeLabel[];
  prompts: PromptMeta[];
  ui_prompts?: { self: string[]; desired_partner: string[] };
  fact_keys?: FactKeyMeta[];
  calibration_version: string;
  calibration_reason_codes: CodeLabel[];
  age: { min: number; max: number; self_min: number };
  distance_km: { min: number; max: number };
};

export type ProfileLocation = { latitude: number; longitude: number };

export type ProfileAnswer = {
  answer_id: string;
  prompt_code: string;
  answer_text: string;
  visibility: string;
  version: number;
};

export type ProfileView = {
  profile_id: string | null;
  version: number;
  display_name: string | null;
  bio: string | null;
  gender_code: string | null;
  orientation_code: string | null;
  search_mode: string | null;
  relationship_goal_code: string | null;
  relationship_status: string | null;
  city_code: string | null;
  public_area_code: string | null;
  location: ProfileLocation | null;
  date_of_birth: string | null;
  visibility: string;
  moderation_state: string;
  activated_at: string | null;
  answers: ProfileAnswer[];
};

export type PreferencesView = {
  version: number;
  search_mode: string | null;
  accepted_gender_codes: string[];
  age_min: number | null;
  age_max: number | null;
  max_distance_km: number | null;
  city_codes: string[];
  relationship_goal_codes: string[];
};

export type OnboardingGates = {
  dob_21_plus: boolean;
  terms_privacy: boolean;
  ai_matching: boolean;
  self_profile: boolean;
  preferences: boolean;
  prompt_answer: boolean;
  facts_reviewed: boolean;
  calibration_done: boolean;
  discoverable: boolean;
};

export type ExtractionStatus = {
  status: string;
  error_code: string | null;
};

export type OnboardingState = {
  flow_version: string;
  policy_version: string;
  onboarding_completed: boolean;
  status: string;
  account_status: string;
  profile: ProfileView;
  preferences: PreferencesView;
  privacy: PrivacyView;
  gates: OnboardingGates;
  steps_completed: string[];
  completion_percent: number;
  pending_jobs?: Array<{ job_type: string; status: string }>;
  extraction?: ExtractionStatus;
  embedding?: ExtractionStatus;
};

export type ProfileFact = {
  fact_id: string;
  profile_side: "self" | "desired_partner";
  fact_code: string;
  value: string;
  preference_strength: string | null;
  review_state: string;
  visibility: string;
  purpose: string;
  confidence: number | null;
  provenance_excerpt: string | null;
  source_type: string;
  source_version: number | null;
  extractor_version: string | null;
  valid_from: string;
  reviewed_at: string | null;
};

export type FactsListResponse = {
  items: ProfileFact[];
  next_cursor: string | null;
  extraction: ExtractionStatus;
};

export type DemoCard = {
  demo_id: string;
  display_name: string;
  summary: string;
};

export type CalibrationSession = {
  calibration_session_id: string;
  calibration_version: string;
  state: string;
  synthetic_only: boolean;
  pairs: Array<{
    demo_pair_id: string;
    label: string;
    left: DemoCard;
    right: DemoCard;
  }>;
  choices: Array<{
    demo_pair_id: string;
    selection: string;
    reason_code: string | null;
  }>;
  label: string;
};

export type OnboardingCompleteResult = {
  status: string;
  flow_version: string;
  profile_version: number;
  preferences_version: number;
  onboarding_completed_at: string | null;
};

export type PublicAnswer = {
  answer_id: string;
  prompt_code: string;
  answer_text: string;
};

export type PublicProfileCard = {
  profile_id: string;
  display_name: string;
  age: number;
  gender_code: string;
  search_mode: string;
  relationship_goal_code: string | null;
  city_code: string;
  public_area_code: string;
};

export type PublicProfile = PublicProfileCard & {
  bio: string | null;
  answers: PublicAnswer[];
  photo_urls?: string[];
};

export type ProfilePhoto = {
  photo_id: string;
  position: number;
  moderation_state: string;
  version: number;
  width: number | null;
  height: number | null;
  preview_url: string;
  created_at: string;
};

export type PhotoIntent = {
  upload_intent_id: string;
  upload_url: string;
  expires_at: string;
  headers: Record<string, string>;
};

export type ProfileListResponse = {
  items: PublicProfileCard[];
  next_cursor: string | null;
};

export type RecommendationReason = {
  version: number;
  codes: string[];
  text: string;
};

export type RecommendationItemView = {
  recommendation_item_id: string;
  rank: number;
  profile: PublicProfile & { photo_urls?: string[] };
  reason: RecommendationReason | null;
  opened?: boolean;
  decision?: "like" | "pass" | null;
};

export type RecommendationBatchView = {
  recommendation_batch_id: string | null;
  status: "ready" | "pending" | "insufficient_supply";
  expires_at: string | null;
  items: RecommendationItemView[];
};

export type MatchSummary = {
  match_id: string;
  conversation_id: string;
  matched_at: string;
};

export type MatchListItem = MatchSummary & {
  counterpart: PublicProfileCard;
};

export type ConversationSummary = {
  conversation_id: string;
  match_id: string;
  last_activity_at: string;
  counterpart: PublicProfileCard;
};

export type MessageView = {
  message_id: string;
  conversation_id: string;
  sender_account_id: string;
  client_message_id: string;
  body: string | null;
  moderation_state: "held" | "allowed" | "rejected";
  created_at: string;
  allowed_at: string | null;
};

export type CursorList<T> = {
  items: T[];
  next_cursor: string | null;
};

export type RecommendationFeedback = {
  action_id: string;
  recommendation_item_id: string;
  decision: "like" | "pass";
  match: MatchSummary | null;
};

export type ReportResult = {
  report_id: string;
  status: string;
};

function remember(session: SessionResponse, persist = true): SessionResponse {
  setSession(
    {
      token: session.session_token,
      accountId: session.account_id,
      expiresAt: session.expires_at,
    },
    persist,
  );
  return session;
}

export const api = {
  getHealth: () => request<HealthStatus>("/healthz"),
  register: (login: string, password: string) =>
    request<SessionResponse>("/v1/auth/local/register", {
      method: "POST",
      body: JSON.stringify({ login, password }),
    }).then(remember),
  login: (login: string, password: string, persist = true) =>
    request<SessionResponse>("/v1/auth/local/sessions", {
      method: "POST",
      body: JSON.stringify({ login, password }),
    }).then((session) => remember(session, persist)),
  loginTelegram: (initData: string) =>
    request<SessionResponse>("/v1/auth/telegram/sessions", {
      method: "POST",
      body: JSON.stringify({ init_data: initData }),
    }).then((session) => remember(session, false)),
  logout: async () => {
    try {
      await request<void>("/v1/auth/sessions/current", { method: "DELETE" });
    } finally {
      setSession(null);
    }
  },
  getPrivacy: () => request<PrivacyView>("/v1/privacy"),
  patchPrivacy: (body: {
    expected_version: number;
    discoverable?: boolean;
    show_distance?: boolean;
    allow_ai_matching?: boolean;
    allow_product_analytics?: boolean;
  }) =>
    request<PrivacyView>("/v1/privacy", {
      method: "PATCH",
      body: JSON.stringify(body),
    }),
  postConsent: (body: { purpose: string; policy_version: string; decision: string }) =>
    request<PrivacyView>("/v1/consents", {
      method: "POST",
      body: JSON.stringify(body),
    }),
  getOnboardingMetadata: () => request<OnboardingMetadata>("/v1/metadata/onboarding"),
  getOnboarding: () => request<OnboardingState>("/v1/onboarding"),
  patchOnboardingProfile: (body: Record<string, unknown>) =>
    request<ProfileView>("/v1/onboarding/profile", {
      method: "PATCH",
      body: JSON.stringify(body),
    }),
  patchOnboardingPreferences: (body: Record<string, unknown>) =>
    request<PreferencesView>("/v1/onboarding/preferences", {
      method: "PATCH",
      body: JSON.stringify(body),
    }),
  patchProfile: (body: Record<string, unknown>) =>
    request<ProfileView>("/v1/profile", {
      method: "PATCH",
      body: JSON.stringify(body),
    }),
  completeOnboarding: (body: {
    expected_profile_version: number;
    expected_preferences_version: number;
  }) =>
    request<OnboardingCompleteResult>("/v1/onboarding/complete", {
      method: "POST",
      body: JSON.stringify(body),
    }),
  getProfileFacts: (state = "pending") =>
    request<FactsListResponse>(
      `/v1/profile/facts?state=${encodeURIComponent(state)}&limit=50`,
    ),
  createProfileFact: (body: {
    fact_code: string;
    value: string;
    profile_side?: string;
    preference_strength?: string;
    visibility?: string;
  }) =>
    request<ProfileFact>("/v1/profile/facts", {
      method: "POST",
      body: JSON.stringify(body),
    }),
  reviewProfileFact: (
    factId: string,
    body: {
      decision: "accept" | "edit" | "reject";
      value?: string;
      visibility?: string;
      expected_source_version?: number | null;
    },
  ) =>
    request<ProfileFact>(`/v1/profile/facts/${factId}/review`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  publishProfile: () =>
    request<{
      status: string;
      activated_at: string | null;
      embedding: ExtractionStatus;
    }>("/v1/profile/publish", {
      method: "POST",
      body: JSON.stringify({}),
    }),
  createCalibrationSession: () =>
    request<CalibrationSession>("/v1/onboarding/calibration-sessions", {
      method: "POST",
      body: JSON.stringify({}),
    }),
  postCalibrationChoice: (
    sessionId: string,
    body: { demo_pair_id: string; selection: "left" | "right" | "neither"; reason_code?: string | null },
  ) =>
    request<CalibrationSession>(`/v1/onboarding/calibration-sessions/${sessionId}/choices`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  completeCalibrationSession: (sessionId: string, decision: "complete" | "skip") =>
    request<CalibrationSession>(`/v1/onboarding/calibration-sessions/${sessionId}/complete`, {
      method: "POST",
      body: JSON.stringify({ decision }),
    }),
  listProfiles: (after?: string | null) => {
    const query = new URLSearchParams({ limit: "50" });
    if (after) {
      query.set("after", after);
    }
    return request<ProfileListResponse>(`/v1/profiles?${query.toString()}`);
  },
  getPublicProfile: (profileId: string) =>
    request<PublicProfile>(`/v1/profiles/${encodeURIComponent(profileId)}`),
  getCurrentRecommendations: () =>
    request<RecommendationBatchView>("/v1/recommendation-batches/current"),
  postRecommendationImpression: (itemId: string, body: { surface: string }) =>
    request<{ exposure_id: string; recommendation_item_id: string }>(
      `/v1/recommendation-items/${encodeURIComponent(itemId)}/impression`,
      { method: "POST", body: JSON.stringify(body) },
    ),
  postRecommendationOpen: (itemId: string, body: { surface: string }) =>
    request<{ action_id: string; recommendation_item_id: string }>(
      `/v1/recommendation-items/${encodeURIComponent(itemId)}/open`,
      { method: "POST", body: JSON.stringify(body) },
    ),
  postRecommendationFeedback: (
    itemId: string,
    body: { action: "like" | "pass"; reason_code?: string },
  ) =>
    request<RecommendationFeedback>(
      `/v1/recommendation-items/${encodeURIComponent(itemId)}/feedback`,
      { method: "POST", body: JSON.stringify(body) },
    ),
  refreshRecommendations: () =>
    request<RecommendationBatchView>("/v1/recommendation-batches/current/refresh", {
      method: "POST",
      body: JSON.stringify({}),
    }),
  postBlock: (body: { profile_id: string; reason_code?: string }) =>
    request<void>("/v1/blocks", {
      method: "POST",
      body: JSON.stringify(body),
    }),
  postReport: (body: { profile_id: string; reason_code: string; details?: string; message_id?: string }) =>
    request<ReportResult>("/v1/reports", {
      method: "POST",
      body: JSON.stringify(body),
    }),
  listMatches: (after?: string | null) => {
    const query = new URLSearchParams({ state: "active", limit: "20" });
    if (after) {
      query.set("after", after);
    }
    return request<CursorList<MatchListItem>>(`/v1/matches?${query.toString()}`);
  },
  unmatch: (matchId: string) =>
    request<void>(`/v1/matches/${encodeURIComponent(matchId)}/unmatch`, {
      method: "POST",
      body: JSON.stringify({}),
    }),
  listConversations: (after?: string | null) => {
    const query = new URLSearchParams({ limit: "20" });
    if (after) {
      query.set("after", after);
    }
    return request<CursorList<ConversationSummary>>(`/v1/conversations?${query.toString()}`);
  },
  listMessages: (conversationId: string, after?: string | null) => {
    const query = new URLSearchParams({ limit: "50" });
    if (after) {
      query.set("after", after);
    }
    return request<CursorList<MessageView>>(
      `/v1/conversations/${encodeURIComponent(conversationId)}/messages?${query.toString()}`,
    );
  },
  sendMessage: (conversationId: string, body: { client_message_id: string; body: string }) =>
    request<MessageView>(`/v1/conversations/${encodeURIComponent(conversationId)}/messages`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  getMessage: (conversationId: string, messageId: string) =>
    request<MessageView>(
      `/v1/conversations/${encodeURIComponent(conversationId)}/messages/${encodeURIComponent(messageId)}`,
    ),
  markConversationRead: (conversationId: string, lastReadMessageId: string) =>
    request<void>(`/v1/conversations/${encodeURIComponent(conversationId)}/read`, {
      method: "POST",
      body: JSON.stringify({ last_read_message_id: lastReadMessageId }),
    }),
  listPhotos: () => request<{ items: ProfilePhoto[] }>("/v1/profile/photos"),
  createPhotoIntent: (body: {
    content_type: string;
    byte_size: number;
    content_sha256: string;
  }) =>
    request<PhotoIntent>("/v1/profile/photos/upload-intents", {
      method: "POST",
      body: JSON.stringify(body),
    }),
  completePhoto: (uploadIntentId: string) =>
    request<ProfilePhoto>(`/v1/profile/photos/${uploadIntentId}/complete`, {
      method: "POST",
      body: JSON.stringify({}),
    }),
  patchPhoto: (photoId: string, body: { expected_version: number; position: number }) =>
    request<ProfilePhoto>(`/v1/profile/photos/${photoId}`, {
      method: "PATCH",
      body: JSON.stringify(body),
    }),
  deletePhoto: (photoId: string) =>
    request<void>(`/v1/profile/photos/${photoId}`, { method: "DELETE" }),
};
