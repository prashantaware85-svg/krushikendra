/**
 * Typed HTTP client for the Krushi Seva backend (Step 4: auth + profile + farms).
 *
 * Only public configuration is used (`NEXT_PUBLIC_API_URL`) — no secrets
 * ever live in frontend code or environment variables.
 *
 * Wire-format note: measurement fields (area, coordinates, soil numerics)
 * travel as JSON **strings** to preserve decimal precision end-to-end.
 * Parse with Number()/parseFloat() for display only.
 */

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export class ApiError extends Error {
  code: string;
  status: number;
  constructor(status: number, code: string, message: string) {
    super(message);
    this.status = status;
    this.code = code;
  }
}

async function request<T>(path: string, init: RequestInit = {}, token?: string): Promise<T> {
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  if (token) headers["Authorization"] = `Bearer ${token}`;
  let res: Response;
  try {
    res = await fetch(`${API_URL}${path}`, { ...init, headers, cache: "no-store" });
  } catch {
    throw new ApiError(0, "NETWORK_ERROR", "Backend unreachable. Is FastAPI running?");
  }
  const body = (await res.json().catch(() => null)) as {
    error?: { code?: string; message?: string };
  } | null;
  if (!res.ok) {
    throw new ApiError(
      res.status,
      body?.error?.code ?? "REQUEST_FAILED",
      body?.error?.message ?? `Request failed (HTTP ${res.status}).`,
    );
  }
  return body as T;
}

/** Multipart variant (FormData sets its own Content-Type boundary). */
async function requestForm<T>(path: string, form: FormData, token?: string): Promise<T> {
  const headers: Record<string, string> = {};
  if (token) headers["Authorization"] = `Bearer ${token}`;
  let res: Response;
  try {
    res = await fetch(`${API_URL}${path}`, {
      method: "POST",
      body: form,
      headers,
      cache: "no-store",
    });
  } catch {
    throw new ApiError(0, "NETWORK_ERROR", "Backend unreachable. Is FastAPI running?");
  }
  const body = (await res.json().catch(() => null)) as {
    error?: { code?: string; message?: string };
  } | null;
  if (!res.ok) {
    throw new ApiError(
      res.status,
      body?.error?.code ?? "REQUEST_FAILED",
      body?.error?.message ?? `Request failed (HTTP ${res.status}).`,
    );
  }
  return body as T;
}

export type SendOtpResponse = {
  message: string;
  mobile_number: string;
  resend_after_seconds: number;
  /** Present ONLY when the backend runs in non-production dev mode. */
  dev_otp?: string | null;
};

export type VerifyOtpResponse = {
  access_token: string;
  refresh_token: string;
  token_type: string;
  expires_in_seconds: number;
  /** Backend contract is snake_case here; mapped at use sites. */
  is_new_user: boolean;
};

export type RefreshResponse = {
  access_token: string;
  refresh_token: string;
  token_type: string;
  expires_in_seconds: number;
};

export type FarmerProfile = {
  full_name: string | null;
  preferred_language: "en" | "hi" | "mr";
  state: string | null;
  district: string | null;
  taluka: string | null;
  village: string | null;
};

export type MeResponse = {
  id: string;
  mobile_number: string;
  is_verified: boolean;
  profile: FarmerProfile | null;
};

export const ACCESS_TOKEN_KEY = "krushi.access_token";

/** Read the stored access token (same key AuthProvider writes). */
export function getStoredToken(): string | null {
  if (typeof window === "undefined") return null;
  return window.localStorage.getItem(ACCESS_TOKEN_KEY);
}

export type AreaUnit = "acre" | "hectare" | "guntha";

export type Farm = {
  id: string;
  farm_name: string;
  area: string;
  area_unit: AreaUnit;
  area_in_acres: number;
  state: string | null;
  district: string | null;
  taluka: string | null;
  village: string | null;
  latitude: string | null;
  longitude: string | null;
  land_type: string | null;
  soil_type: string | null;
  irrigation_type: string | null;
  water_source: string | null;
  ownership_type: string | null;
};

export type FarmWrite = {
  farm_name: string;
  area: string | number;
  area_unit: AreaUnit;
  state?: string | null;
  district?: string | null;
  taluka?: string | null;
  village?: string | null;
  latitude?: string | number | null;
  longitude?: string | number | null;
  land_type?: string | null;
  soil_type?: string | null;
  irrigation_type?: string | null;
  water_source?: string | null;
  ownership_type?: string | null;
};

export type Soil = {
  id: string;
  farm_id: string;
  soil_type: string | null;
  soil_test_available: boolean;
  soil_test_date: string | null;
  ph: string | null;
  organic_carbon: string | null;
  nitrogen: string | null;
  phosphorus: string | null;
  potassium: string | null;
  soil_test_document_reference: string | null;
};

export type SoilWrite = {
  soil_type?: string | null;
  soil_test_available?: boolean;
  soil_test_date?: string | null;
  ph?: string | number | null;
  organic_carbon?: string | number | null;
  nitrogen?: string | number | null;
  phosphorus?: string | number | null;
  potassium?: string | number | null;
  soil_test_document_reference?: string | null;
};

export type Crop = {
  id: string;
  farm_id: string;
  crop_variety_id: string | null;
  crop_name: string;
  variety_name: string | null;
  area: string;
  area_unit: AreaUnit;
  area_in_acres: number;
  season: string;
  sowing_date: string;
  expected_harvest_date: string | null;
  status: string;
  notes: string | null;
};

export type CropWrite = {
  crop_name: string;
  variety_name?: string | null;
  crop_variety_id?: string | null;
  area: string | number;
  area_unit: AreaUnit;
  season?: string;
  sowing_date: string;
  expected_harvest_date?: string | null;
  status?: string;
  notes?: string | null;
};

export type CropVariety = {
  id: string;
  crop_name: string;
  variety_name: string | null;
  crop_category: string;
};

export type WeatherCurrent = {
  latitude: string;
  longitude: string;
  data_state: "fresh" | "cached" | "stale";
  provider: string;
  temperature: string | null;
  feels_like: string | null;
  humidity: number | null;
  precipitation_probability: number | null;
  precipitation_amount: string | null;
  wind_speed: string | null;
  wind_direction: number | null;
  condition: string;
  description: string | null;
  observed_at: string | null;
};

export type ForecastDay = {
  date: string;
  temp_min: string | null;
  temp_max: string | null;
  humidity: number | null;
  precipitation_probability: number | null;
  precipitation_amount: string | null;
  wind_speed: string | null;
  condition: string;
  description: string | null;
};

export type WeatherForecast = {
  latitude: string;
  longitude: string;
  data_state: "fresh" | "cached" | "stale";
  provider: string;
  days: ForecastDay[];
};

export type Commodity = {
  id: string;
  name: string;
  category: string;
  local_name: string | null;
};

export type MarketInfo = {
  id: string;
  name: string;
  state: string;
  district: string;
  taluka: string | null;
  village: string | null;
  latitude: string | null;
  longitude: string | null;
  distance_km?: number;
};

export type MarketPrice = {
  id: string;
  market: MarketInfo;
  commodity: Commodity;
  price_date: string;
  min_price: string;
  max_price: string;
  modal_price: string;
  unit: string;
  currency: string;
  source: string;
  is_sample: boolean;
  fetched_at: string;
};

export type PricesResponse = {
  data_state: "fresh" | "cached" | "stale";
  prices: MarketPrice[];
  limit: number;
  offset: number;
};

export type HistoryResponse = {
  data_state: "fresh" | "cached" | "stale";
  prices: MarketPrice[];
};

export type FarmMarketEntry = {
  market: MarketInfo;
  prices: MarketPrice[];
};

export type AIConversation = {
  id: string;
  title: string | null;
  language: string;
};

export type AISource = {
  document_id: string;
  chunk_id: string;
  title: string;
  source_name: string;
  source_url: string | null;
  score: number;
};

export type AIMessage = {
  id: string;
  conversation_id: string;
  role: "user" | "assistant";
  content: string;
  sources: AISource[];
};

export type AIConversationDetail = AIConversation & {
  messages: AIMessage[];
};

export type ChatReply = {
  conversation_id: string;
  message: AIMessage;
  sources: AISource[];
};

export type FarmMarketResponse = {
  farm_id: string;
  data_state: "fresh" | "cached" | "stale";
  markets: FarmMarketEntry[];
};

export type ProductCategory = {
  id: string;
  name: string;
  slug: string;
  description: string | null;
  parent_id: string | null;
};

export type ProductVariant = {
  id: string;
  pack_size: string;
  pack_unit: string;
  sku: string | null;
  mrp: string | null;
  selling_price: string | null;
  stock_status: string;
};

export type ProductImageMeta = {
  id: string;
  alt_text: string | null;
  sort_order: number;
  is_primary: boolean;
};

export type CartItem = {
  item_id: string;
  variant_id: string;
  variant_name: string;
  product_name: string | null;
  qty: number;
  unit_price_paise: number | null;
  line_total_paise: number | null;
  price_on_request: boolean;
};

export type Cart = {
  items: CartItem[];
  subtotal_paise: number;
  currency: string;
};

export type CartIssue = {
  code: string;
  message: string;
  item_id: string | null;
  variant_id: string | null;
};

export type Address = {
  id: string;
  label: string | null;
  line1: string;
  city: string;
  state: string;
  pincode: string;
  phone: string;
  is_default: boolean;
};

export type AddressWrite = {
  label?: string | null;
  line1: string;
  city: string;
  state: string;
  pincode: string;
  phone: string;
};

export type OrderItem = {
  id: string;
  variant_id: string | null;
  qty: number;
  unit_price_paise: number;
  line_total_paise: number;
};

export type Order = {
  id: string;
  order_number: string | null;
  status: string;
  payment_status: string;
  subtotal_paise: number;
  delivery_paise: number;
  total_paise: number;
  payment_ref: string | null;
  address_id: string | null;
  created_at: string;
  items: OrderItem[];
};

export type Payment = {
  id: string;
  order_id: string;
  provider: string;
  provider_ref: string;
  amount_paise: number;
  currency: string;
  status: string;
  idempotency_key: string;
};

export type PaymentInitiate = Payment & {
  redirect_url: string;
  approved: boolean;
};

export type KhataSummary = {
  total_debits_paise: number;
  total_credits_paise: number;
  total_payments_paise: number;
  outstanding_paise: number;
  credit_limit_paise: number;
  over_limit: boolean;
  currency: string;
};

export type KhataEntry = {
  id: string;
  entry_type: string;
  amount_paise: number;
  balance_after_paise: number;
  order_id: string | null;
  note: string | null;
  created_at: string;
};

export type KhataEntriesPage = {
  entries: KhataEntry[];
  total: number;
  limit: number;
  offset: number;
};

export type StoreProduct = {
  id: string;
  name: string;
  slug: string;
  short_description: string | null;
  description: string | null;
  brand: string | null;
  manufacturer: string | null;
  product_type: string;
  category_id: string | null;
  category_name: string | null;
  registration_number: string | null;
  is_verified: boolean;
};

export type StoreProductDetail = StoreProduct & {
  variants: ProductVariant[];
  images: ProductImageMeta[];
};

export type PestDisease = {
  id: string;
  name: string;
  local_name: string | null;
  scientific_name: string | null;
  category: string | null;
  description: string | null;
  is_verified: boolean;
};

export type HealthObservation = {
  id: string;
  farm_crop_id: string;
  observation_type: string;
  pest_id: string | null;
  pest_name: string | null;
  disease_id: string | null;
  disease_name: string | null;
  observed_name: string | null;
  observation_date: string;
  severity: string;
  affected_area: string | null;
  affected_area_unit: string | null;
  symptoms: string | null;
  notes: string | null;
  status: string;
  source: string;
  has_photos: boolean;
  linked_analysis: {
    id: string;
    possible_condition: string | null;
    confidence: string | null;
    status: string;
  } | null;
};

export type HealthObservationWrite = {
  observation_type: string;
  pest_id?: string | null;
  disease_id?: string | null;
  observed_name?: string | null;
  observation_date: string;
  severity: string;
  affected_area?: string | number | null;
  affected_area_unit?: string | null;
  symptoms?: string | null;
  notes?: string | null;
  status?: string;
  source?: string;
  linked_image_analysis_id?: string | null;
};

export type HealthAction = {
  id: string;
  observation_id: string;
  action_date: string;
  action_type: string;
  description: string;
  product_name: string | null;
  quantity: string | null;
  quantity_unit: string | null;
  notes: string | null;
};

export type HealthActionWrite = {
  action_date: string;
  action_type: string;
  description: string;
  product_name?: string | null;
  quantity?: string | number | null;
  quantity_unit?: string | null;
  notes?: string | null;
};

export type SoilTest = {
  id: string;
  farm_id: string;
  test_date: string;
  laboratory_name: string | null;
  report_number: string | null;
  soil_type: string | null;
  ph: string | null;
  electrical_conductivity: string | null;
  organic_carbon: string | null;
  nitrogen: string | null;
  phosphorus: string | null;
  potassium: string | null;
  sulphur: string | null;
  zinc: string | null;
  iron: string | null;
  manganese: string | null;
  copper: string | null;
  boron: string | null;
  notes: string | null;
  has_report: boolean;
};

export type SoilTestWrite = {
  test_date: string;
  laboratory_name?: string | null;
  report_number?: string | null;
  soil_type?: string | null;
  ph?: string | number | null;
  electrical_conductivity?: string | number | null;
  organic_carbon?: string | number | null;
  nitrogen?: string | number | null;
  phosphorus?: string | number | null;
  potassium?: string | number | null;
  sulphur?: string | number | null;
  zinc?: string | number | null;
  iron?: string | number | null;
  manganese?: string | number | null;
  copper?: string | number | null;
  boron?: string | number | null;
  notes?: string | null;
};

export type Fertilizer = {
  id: string;
  farm_crop_id: string;
  application_date: string;
  fertilizer_name: string;
  fertilizer_type: string | null;
  quantity: string;
  quantity_unit: string;
  application_method: string | null;
  purpose: string | null;
  notes: string | null;
};

export type FertilizerWrite = {
  application_date: string;
  fertilizer_name: string;
  fertilizer_type?: string | null;
  quantity: string | number;
  quantity_unit: string;
  application_method?: string | null;
  purpose?: string | null;
  notes?: string | null;
  record_activity?: boolean;
};

export type VisionSource = {
  document_id: string;
  chunk_id: string;
  title: string;
  source_name: string;
  source_url: string | null;
  score: number;
};

export type CropAnalysis = {
  id: string;
  farm_id: string;
  farm_crop_id: string;
  status: string;
  provider: string;
  model: string;
  possible_condition: string | null;
  confidence: string | null;
  observations: string[];
  needs_info: string[];
  next_steps: string[];
  image_quality: string | null;
  quality_notes: string | null;
  disclaimer: string;
  sources: VisionSource[];
  response_language: string;
  is_mock: boolean;
};

export type AnalysisHistoryItem = {
  id: string;
  farm_id: string;
  farm_crop_id: string;
  crop_name: string | null;
  status: string;
  possible_condition: string | null;
  confidence: string | null;
  created_at: string;
};

export type Activity = {
  id: string;
  farm_crop_id: string;
  activity_type: string;
  title: string;
  description: string | null;
  activity_date: string;
  status: string;
  quantity: string | null;
  quantity_unit: string | null;
  cost: string | null;
  notes: string | null;
  created_at: string;
};

export type ActivityWrite = {
  activity_type: string;
  title: string;
  description?: string | null;
  activity_date: string;
  status?: string;
  quantity?: string | number | null;
  quantity_unit?: string | null;
  cost?: string | number | null;
  notes?: string | null;
};

export type Timeline = {
  farm_id: string;
  crop_id: string;
  crop_name: string;
  activities: Activity[];
};

/** ── Step 16: suppliers / purchases / inventory (store back-office) ── */

export type Supplier = {
  id: string;
  name: string;
  mobile_number: string | null;
  email: string | null;
  address: string | null;
  gstin: string | null;
  notes: string | null;
  is_active: boolean;
};

export type SupplierWrite = {
  name: string;
  mobile_number?: string | null;
  email?: string | null;
  address?: string | null;
  gstin?: string | null;
  notes?: string | null;
  is_active?: boolean;
};

export type PurchaseItem = {
  id: string;
  variant_id: string;
  variant_name: string | null;
  qty: string;
  unit_cost_paise: number;
  line_total_paise: number;
};

export type Purchase = {
  id: string;
  supplier_id: string | null;
  supplier_name: string | null;
  purchase_date: string | null;
  status: string;
  subtotal_paise: number;
  discount_paise: number;
  other_charges_paise: number;
  total_paise: number;
  notes: string | null;
  items: PurchaseItem[];
};

export type PurchaseWrite = {
  supplier_id?: string | null;
  purchase_date?: string | null;
  discount_paise?: number;
  other_charges_paise?: number;
  notes?: string | null;
};

export type PurchaseItemWrite = {
  variant_id: string;
  qty: string | number;
  unit_cost_paise: number;
};

export type InventoryItem = {
  variant_id: string;
  product_name: string | null;
  variant_name: string | null;
  qty_on_hand: string;
  qty_reserved: string;
  available: string;
  reorder_level: string | null;
  status: "in_stock" | "low_stock" | "out_of_stock";
};

export type InventoryList = {
  items: InventoryItem[];
  total: number;
};

export type InventorySummary = {
  total_variants: number;
  out_of_stock: number;
  low_stock: number;
  in_stock: number;
  recent_movements: StockMovement[];
};

export type InventoryDetail = InventoryItem & {
  product_id: string | null;
  sku: string | null;
  /** Step 17: reorder quantity — backend may serialise as reorder_quantity or reorder_qty. */
  reorder_quantity?: string | null;
  reorder_qty?: string | null;
};

export type StockMovement = {
  id: string;
  variant_id: string;
  movement_type: string;
  quantity: string;
  qty_before: string | null;
  qty_after: string | null;
  reason: string | null;
  created_at: string;
};

export type MovementPage = {
  movements: StockMovement[];
  total: number;
  limit: number;
  offset: number;
};

/** ── Step 17: store staff RBAC + reorder levels (admin/manager/staff) ── */

export type StaffRole = "admin" | "store_manager" | "store_staff";

export type StaffMember = {
  id: string;
  user_id: string | null;
  mobile: string | null;
  /** Alias when the backend serialises as mobile_number. */
  mobile_number?: string | null;
  display_name: string | null;
  role: StaffRole | string;
  is_active: boolean;
  created_at: string;
};

export type StaffCreate = {
  mobile_number?: string | null;
  user_id?: string | null;
  role: StaffRole;
};

export type StaffUpdate = {
  role?: StaffRole;
  is_active?: boolean;
};

/** Create + update shapes (POST takes mobile/user + role; PUT takes role/active). */
export type StaffWrite = StaffCreate & StaffUpdate;

export type ReorderWrite = {
  reorder_level: string | number;
  reorder_quantity?: string | number | null;
};

/** ── Step 18: POS counter billing (staff roles; cancel = manager+) ── */

export type PosProduct = {
  variant_id: string;
  product_id: string | null;
  product_name: string | null;
  variant_name: string | null;
  unit_price_paise: number | null;
  price_on_request: boolean;
  /** Decimal quantity string (exact, no float). */
  available: string;
  /** Backend-computed availability badge: "🟢" | "🟠" | "🔴". */
  stock_status: string;
};

/**
 * Task-spec envelope {items,total}; the backend currently returns a bare
 * array — listPosProducts() accepts both and always resolves PosProduct[].
 */
export type PosProductPage = {
  items: PosProduct[];
  total: number;
};

export type PosBillItem = {
  id: string;
  variant_id: string;
  product_name_snapshot: string;
  variant_name_snapshot: string;
  /** Decimal quantity string. */
  qty: string;
  unit_price_paise: number;
  discount_paise: number;
  line_total_paise: number;
};

export type PosBill = {
  id: string;
  bill_number: string;
  customer_id: string | null;
  subtotal_paise: number;
  discount_paise: number;
  other_charges_paise: number;
  total_paise: number;
  payment_status: string;
  sale_status: string;
  payment_mode: string | null;
  amount_received_paise: number | null;
  amount_paid_paise: number;
  balance_due_paise: number;
  payment_reference: string | null;
  notes: string | null;
  created_at: string;
  updated_at: string;
  items: PosBillItem[];
};

export type PosBillItemIn = {
  variant_id: string;
  qty: string | number;
};

export type PosBillCreate = {
  items: PosBillItemIn[];
  customer_id?: string | null;
  discount_paise?: number;
  other_charges_paise?: number;
  payment_mode?: string | null;
  notes?: string | null;
};

export type PosBillCompleteIn = {
  payment_mode: string;
  amount_received_paise?: number | null;
  payment_reference?: string | null;
  amount_paid_paise?: number | null;
};

/**
 * Backend returns {bill, duplicate}; change is derived client-side for
 * display (received − paid) and carried here when known.
 */
export type PosBillCompleteOut = {
  bill: PosBill;
  duplicate: boolean;
  change_paise?: number | null;
};

export type PosBillCancelIn = {
  reason?: string | null;
};

export type PosBillCancelOut = {
  bill: PosBill;
  duplicate: boolean;
};

export type PosBillFilters = {
  bill_number?: string;
  customer_id?: string;
  payment_mode?: string;
  payment_status?: string;
  sale_status?: string;
  date_from?: string;
  date_to?: string;
  limit?: number;
  offset?: number;
};

export type PosBillPage = {
  bills: PosBill[];
  total: number;
  limit: number;
  offset: number;
};

export type PosReceiptItem = {
  product_name: string;
  variant_name: string;
  /** Decimal quantity string. */
  qty: string;
  unit_price_paise: number;
  line_total_paise: number;
};

export type PosReceiptPayment = {
  mode: string | null;
  paid_paise: number | null;
  received_paise?: number | null;
  change_paise?: number | null;
  balance_due_paise?: number | null;
  reference?: string | null;
  refund_note?: string | null;
};

export type PosReceipt = {
  store: Record<string, string | number | null>;
  bill_number: string;
  created_at: string;
  cashier: string;
  customer: string | null;
  items: PosReceiptItem[];
  subtotal_paise: number;
  discount_paise: number;
  other_charges_paise: number;
  total_paise: number;
  sale_status: string;
  payment_status: string;
  payment: PosReceiptPayment;
  footer: string;
};

export type PosSummary = {
  date: string;
  bills: number;
  total_paise: number;
  breakdown: Record<string, { bills: number; total_paise: number }>;
};

/** Bill-line product display name (backend snapshot field is authoritative). */
export function posItemProductName(item: PosBillItem): string {
  return item.product_name_snapshot || item.variant_id.slice(0, 8);
}

/** Bill-line variant display name (backend snapshot field). */
export function posItemVariantName(item: PosBillItem): string {
  return item.variant_name_snapshot || "";
}

export const api = {
  sendOtp: (mobile_number: string) =>
    request<SendOtpResponse>("/api/v1/auth/send-otp", {
      method: "POST",
      body: JSON.stringify({ mobile_number }),
    }),
  verifyOtp: (mobile_number: string, otp: string) =>
    request<VerifyOtpResponse>("/api/v1/auth/verify-otp", {
      method: "POST",
      body: JSON.stringify({ mobile_number, otp }),
    }),
  refresh: (refresh_token: string) =>
    request<RefreshResponse>("/api/v1/auth/refresh", {
      method: "POST",
      body: JSON.stringify({ refresh_token }),
    }),
  logout: (refresh_token: string) =>
    request<{ message: string }>("/api/v1/auth/logout", {
      method: "POST",
      body: JSON.stringify({ refresh_token }),
    }),
  me: (accessToken: string) => request<MeResponse>("/api/v1/auth/me", {}, accessToken),
  getProfile: (accessToken: string) =>
    request<FarmerProfile>("/api/v1/farmer/profile", {}, accessToken),
  updateProfile: (accessToken: string, patch: Partial<FarmerProfile>) =>
    request<FarmerProfile>("/api/v1/farmer/profile", {
      method: "PUT",
      body: JSON.stringify(patch),
    }, accessToken),
  listFarms: (accessToken: string) =>
    request<Farm[]>("/api/v1/farms", {}, accessToken),
  createFarm: (accessToken: string, payload: FarmWrite) =>
    request<Farm>("/api/v1/farms", {
      method: "POST",
      body: JSON.stringify(payload),
    }, accessToken),
  getFarm: (accessToken: string, id: string) =>
    request<Farm>(`/api/v1/farms/${id}`, {}, accessToken),
  updateFarm: (accessToken: string, id: string, patch: Partial<FarmWrite>) =>
    request<Farm>(`/api/v1/farms/${id}`, {
      method: "PUT",
      body: JSON.stringify(patch),
    }, accessToken),
  deleteFarm: (accessToken: string, id: string) =>
    request<void>(`/api/v1/farms/${id}`, { method: "DELETE" }, accessToken),
  getSoil: (accessToken: string, farmId: string) =>
    request<Soil>(`/api/v1/farms/${farmId}/soil`, {}, accessToken),
  createSoil: (accessToken: string, farmId: string, payload: SoilWrite) =>
    request<Soil>(`/api/v1/farms/${farmId}/soil`, {
      method: "POST",
      body: JSON.stringify(payload),
    }, accessToken),
  updateSoil: (accessToken: string, farmId: string, patch: SoilWrite) =>
    request<Soil>(`/api/v1/farms/${farmId}/soil`, {
      method: "PUT",
      body: JSON.stringify(patch),
    }, accessToken),
  listCrops: (accessToken: string, farmId: string) =>
    request<Crop[]>(`/api/v1/farms/${farmId}/crops`, {}, accessToken),
  createCrop: (accessToken: string, farmId: string, payload: CropWrite) =>
    request<Crop>(`/api/v1/farms/${farmId}/crops`, {
      method: "POST",
      body: JSON.stringify(payload),
    }, accessToken),
  getCrop: (accessToken: string, farmId: string, cropId: string) =>
    request<Crop>(`/api/v1/farms/${farmId}/crops/${cropId}`, {}, accessToken),
  updateCrop: (accessToken: string, farmId: string, cropId: string, patch: Partial<CropWrite>) =>
    request<Crop>(`/api/v1/farms/${farmId}/crops/${cropId}`, {
      method: "PUT",
      body: JSON.stringify(patch),
    }, accessToken),
  deleteCrop: (accessToken: string, farmId: string, cropId: string) =>
    request<void>(`/api/v1/farms/${farmId}/crops/${cropId}`, { method: "DELETE" }, accessToken),
  listVarieties: (accessToken: string) =>
    request<CropVariety[]>("/api/v1/crop-varieties", {}, accessToken),
  listActivities: (accessToken: string, farmId: string, cropId: string) =>
    request<Activity[]>(`/api/v1/farms/${farmId}/crops/${cropId}/activities`, {}, accessToken),
  createActivity: (accessToken: string, farmId: string, cropId: string, payload: ActivityWrite) =>
    request<Activity>(`/api/v1/farms/${farmId}/crops/${cropId}/activities`, {
      method: "POST",
      body: JSON.stringify(payload),
    }, accessToken),
  getActivity: (accessToken: string, farmId: string, cropId: string, activityId: string) =>
    request<Activity>(`/api/v1/farms/${farmId}/crops/${cropId}/activities/${activityId}`, {}, accessToken),
  updateActivity: (accessToken: string, farmId: string, cropId: string, activityId: string, patch: Partial<ActivityWrite>) =>
    request<Activity>(`/api/v1/farms/${farmId}/crops/${cropId}/activities/${activityId}`, {
      method: "PUT",
      body: JSON.stringify(patch),
    }, accessToken),
  deleteActivity: (accessToken: string, farmId: string, cropId: string, activityId: string) =>
    request<void>(`/api/v1/farms/${farmId}/crops/${cropId}/activities/${activityId}`, { method: "DELETE" }, accessToken),
  getTimeline: (accessToken: string, farmId: string, cropId: string) =>
    request<Timeline>(`/api/v1/farms/${farmId}/crops/${cropId}/timeline`, {}, accessToken),
  weatherCurrent: (accessToken: string, farmId: string) =>
    request<WeatherCurrent>(`/api/v1/farms/${farmId}/weather/current`, {}, accessToken),
  weatherForecast: (accessToken: string, farmId: string) =>
    request<WeatherForecast>(`/api/v1/farms/${farmId}/weather/forecast`, {}, accessToken),
  listCommodities: (accessToken: string, search?: string) =>
    request<Commodity[]>(
      `/api/v1/market/commodities${search ? `?search=${encodeURIComponent(search)}` : ""}`,
      {},
      accessToken,
    ),
  getCommodity: (accessToken: string, id: string) =>
    request<Commodity>(`/api/v1/market/commodities/${id}`, {}, accessToken),
  listMarkets: (accessToken: string) =>
    request<MarketInfo[]>(`/api/v1/market/markets`, {}, accessToken),
  marketPrices: (accessToken: string, query: string) =>
    request<PricesResponse>(`/api/v1/market/prices${query}`, {}, accessToken),
  priceHistory: (accessToken: string, query: string) =>
    request<HistoryResponse>(`/api/v1/market/prices/history${query}`, {}, accessToken),
  farmMarketPrices: (accessToken: string, farmId: string) =>
    request<FarmMarketResponse>(`/api/v1/farms/${farmId}/market-prices`, {}, accessToken),
  listConversations: (accessToken: string) =>
    request<AIConversation[]>(`/api/v1/ai/conversations`, {}, accessToken),
  createConversation: (accessToken: string, language: string) =>
    request<AIConversation>(`/api/v1/ai/conversations`, {
      method: "POST",
      body: JSON.stringify({ language }),
    }, accessToken),
  getConversation: (accessToken: string, id: string) =>
    request<AIConversationDetail>(`/api/v1/ai/conversations/${id}`, {}, accessToken),
  deleteConversation: (accessToken: string, id: string) =>
    request<void>(`/api/v1/ai/conversations/${id}`, { method: "DELETE" }, accessToken),
  sendChatMessage: (
    accessToken: string,
    id: string,
    payload: { message: string; farm_id?: string | null; crop_id?: string | null; language?: string },
  ) =>
    request<ChatReply>(`/api/v1/ai/conversations/${id}/messages`, {
      method: "POST",
      body: JSON.stringify(payload),
    }, accessToken),
  uploadCropImages: (
    accessToken: string,
    payload: { farm_id: string; crop_id: string; language?: string; files: File[] },
  ) => {
    const form = new FormData();
    form.append("farm_id", payload.farm_id);
    form.append("crop_id", payload.crop_id);
    if (payload.language) form.append("language", payload.language);
    for (const file of payload.files.slice(0, 3)) form.append("images", file);
    return requestForm<CropAnalysis>("/api/v1/crop-images", form, accessToken);
  },
  listAnalyses: (accessToken: string) =>
    request<AnalysisHistoryItem[]>(`/api/v1/crop-images`, {}, accessToken),
  getAnalysis: (accessToken: string, id: string) =>
    request<CropAnalysis>(`/api/v1/crop-images/${id}`, {}, accessToken),
  reanalyze: (accessToken: string, id: string) =>
    request<CropAnalysis>(`/api/v1/crop-images/${id}/analyze`, { method: "POST" }, accessToken),
  deleteAnalysis: (accessToken: string, id: string) =>
    request<void>(`/api/v1/crop-images/${id}`, { method: "DELETE" }, accessToken),
  analysisImageUrl: (id: string) =>
    `${API_URL}/api/v1/crop-images/${id}/image`,
  listSoilTests: (accessToken: string, farmId: string) =>
    request<SoilTest[]>(`/api/v1/farms/${farmId}/soil-tests`, {}, accessToken),
  createSoilTest: (accessToken: string, farmId: string, payload: SoilTestWrite) =>
    request<SoilTest>(`/api/v1/farms/${farmId}/soil-tests`, {
      method: "POST",
      body: JSON.stringify(payload),
    }, accessToken),
  getSoilTest: (accessToken: string, farmId: string, testId: string) =>
    request<SoilTest>(`/api/v1/farms/${farmId}/soil-tests/${testId}`, {}, accessToken),
  updateSoilTest: (accessToken: string, farmId: string, testId: string, patch: Partial<SoilTestWrite>) =>
    request<SoilTest>(`/api/v1/farms/${farmId}/soil-tests/${testId}`, {
      method: "PUT",
      body: JSON.stringify(patch),
    }, accessToken),
  deleteSoilTest: (accessToken: string, farmId: string, testId: string) =>
    request<void>(`/api/v1/farms/${farmId}/soil-tests/${testId}`, { method: "DELETE" }, accessToken),
  uploadSoilReport: (accessToken: string, farmId: string, testId: string, file: File) => {
    const form = new FormData();
    form.append("report", file);
    return requestForm<SoilTest>(
      `/api/v1/farms/${farmId}/soil-tests/${testId}/report`, form, accessToken,
    );
  },
  soilReportBlob: async (accessToken: string, farmId: string, testId: string) => {
    // Authed byte fetch (no public file URLs by design).
    const res = await fetch(
      `${API_URL}/api/v1/farms/${farmId}/soil-tests/${testId}/report`,
      { headers: { Authorization: `Bearer ${accessToken}` }, cache: "no-store" },
    );
    if (!res.ok) {
      const body = (await res.json().catch(() => null)) as {
        error?: { code?: string; message?: string };
      } | null;
      throw new ApiError(
        res.status,
        body?.error?.code ?? "REQUEST_FAILED",
        body?.error?.message ?? `Request failed (HTTP ${res.status}).`,
      );
    }
    return { blob: await res.blob(), contentType: res.headers.get("content-type") };
  },
  listFertilizers: (accessToken: string, farmId: string, cropId: string) =>
    request<Fertilizer[]>(`/api/v1/farms/${farmId}/crops/${cropId}/fertilizers`, {}, accessToken),
  createFertilizer: (accessToken: string, farmId: string, cropId: string, payload: FertilizerWrite) =>
    request<Fertilizer>(`/api/v1/farms/${farmId}/crops/${cropId}/fertilizers`, {
      method: "POST",
      body: JSON.stringify(payload),
    }, accessToken),
  getFertilizer: (accessToken: string, farmId: string, cropId: string, fertId: string) =>
    request<Fertilizer>(`/api/v1/farms/${farmId}/crops/${cropId}/fertilizers/${fertId}`, {}, accessToken),
  updateFertilizer: (accessToken: string, farmId: string, cropId: string, fertId: string, patch: Partial<FertilizerWrite>) =>
    request<Fertilizer>(`/api/v1/farms/${farmId}/crops/${cropId}/fertilizers/${fertId}`, {
      method: "PUT",
      body: JSON.stringify(patch),
    }, accessToken),
  deleteFertilizer: (accessToken: string, farmId: string, cropId: string, fertId: string) =>
    request<void>(`/api/v1/farms/${farmId}/crops/${cropId}/fertilizers/${fertId}`, { method: "DELETE" }, accessToken),
  listPests: (accessToken: string) =>
    request<PestDisease[]>(`/api/v1/pests`, {}, accessToken),
  listDiseases: (accessToken: string) =>
    request<PestDisease[]>(`/api/v1/diseases`, {}, accessToken),
  listObservations: (accessToken: string, farmId: string, cropId: string) =>
    request<HealthObservation[]>(`/api/v1/farms/${farmId}/crops/${cropId}/health`, {}, accessToken),
  createObservation: (accessToken: string, farmId: string, cropId: string, payload: HealthObservationWrite) =>
    request<HealthObservation>(`/api/v1/farms/${farmId}/crops/${cropId}/health`, {
      method: "POST",
      body: JSON.stringify(payload),
    }, accessToken),
  getObservation: (accessToken: string, farmId: string, cropId: string, obsId: string) =>
    request<HealthObservation>(`/api/v1/farms/${farmId}/crops/${cropId}/health/${obsId}`, {}, accessToken),
  updateObservation: (accessToken: string, farmId: string, cropId: string, obsId: string, patch: Partial<HealthObservationWrite>) =>
    request<HealthObservation>(`/api/v1/farms/${farmId}/crops/${cropId}/health/${obsId}`, {
      method: "PUT",
      body: JSON.stringify(patch),
    }, accessToken),
  deleteObservation: (accessToken: string, farmId: string, cropId: string, obsId: string) =>
    request<void>(`/api/v1/farms/${farmId}/crops/${cropId}/health/${obsId}`, { method: "DELETE" }, accessToken),
  uploadObservationPhotos: (accessToken: string, farmId: string, cropId: string, obsId: string, files: File[]) => {
    const form = new FormData();
    for (const file of files.slice(0, 3)) form.append("photos", file);
    return requestForm<HealthObservation>(
      `/api/v1/farms/${farmId}/crops/${cropId}/health/${obsId}/photos`, form, accessToken,
    );
  },
  listActions: (accessToken: string, obsId: string) =>
    request<HealthAction[]>(`/api/v1/health/${obsId}/actions`, {}, accessToken),
  createAction: (accessToken: string, obsId: string, payload: HealthActionWrite) =>
    request<HealthAction>(`/api/v1/health/${obsId}/actions`, {
      method: "POST",
      body: JSON.stringify(payload),
    }, accessToken),
  updateAction: (accessToken: string, obsId: string, actionId: string, patch: Partial<HealthActionWrite>) =>
    request<HealthAction>(`/api/v1/health/${obsId}/actions/${actionId}`, {
      method: "PUT",
      body: JSON.stringify(patch),
    }, accessToken),
  deleteAction: (accessToken: string, obsId: string, actionId: string) =>
    request<void>(`/api/v1/health/${obsId}/actions/${actionId}`, { method: "DELETE" }, accessToken),
  listStoreCategories: (accessToken: string) =>
    request<ProductCategory[]>(`/api/v1/store/categories`, {}, accessToken),
  listStoreProducts: (
    accessToken: string,
    filters: { search?: string; category_id?: string; product_type?: string; brand?: string; stock_status?: string } = {},
  ) => {
    const params = new URLSearchParams();
    if (filters.search) params.set("search", filters.search);
    if (filters.category_id) params.set("category_id", filters.category_id);
    if (filters.product_type) params.set("product_type", filters.product_type);
    if (filters.brand) params.set("brand", filters.brand);
    if (filters.stock_status) params.set("stock_status", filters.stock_status);
    const query = params.toString();
    return request<{ products: StoreProduct[]; limit: number; offset: number }>(
      `/api/v1/store/products${query ? `?${query}` : ""}`, {}, accessToken,
    );
  },
  getStoreProduct: (accessToken: string, id: string) =>
    request<StoreProductDetail>(`/api/v1/store/products/${id}`, {}, accessToken),
  storeImageBlob: async (accessToken: string, imageId: string) => {
    // Authed byte fetch (no public file URLs by design).
    const res = await fetch(`${API_URL}/api/v1/store/images/${imageId}`, {
      headers: { Authorization: `Bearer ${accessToken}` },
      cache: "no-store",
    });
    if (!res.ok) {
      const body = (await res.json().catch(() => null)) as {
        error?: { code?: string; message?: string };
      } | null;
      throw new ApiError(
        res.status,
        body?.error?.code ?? "REQUEST_FAILED",
        body?.error?.message ?? `Request failed (HTTP ${res.status}).`,
      );
    }
    return res.blob();
  },
  getCart: (accessToken: string) =>
    request<Cart>(`/api/v1/store/cart`, {}, accessToken),
  addCartItem: (accessToken: string, variant_id: string, qty: number) =>
    request<CartItem>(`/api/v1/store/cart/items`, {
      method: "POST",
      body: JSON.stringify({ variant_id, qty }),
    }, accessToken),
  updateCartItem: (accessToken: string, itemId: string, qty: number) =>
    request<CartItem>(`/api/v1/store/cart/items/${itemId}`, {
      method: "PUT",
      body: JSON.stringify({ qty }),
    }, accessToken),
  removeCartItem: (accessToken: string, itemId: string) =>
    request<void>(`/api/v1/store/cart/items/${itemId}`, { method: "DELETE" }, accessToken),
  clearCart: (accessToken: string) =>
    request<void>(`/api/v1/store/cart`, { method: "DELETE" }, accessToken),
  validateCart: (accessToken: string) =>
    request<{ valid: boolean; issues: CartIssue[]; subtotal_paise: number }>(
      `/api/v1/store/cart/validate`, { method: "POST" }, accessToken,
    ),
  listAddresses: (accessToken: string) =>
    request<Address[]>(`/api/v1/store/addresses`, {}, accessToken),
  createAddress: (accessToken: string, payload: AddressWrite) =>
    request<Address>(`/api/v1/store/addresses`, {
      method: "POST",
      body: JSON.stringify(payload),
    }, accessToken),
  updateAddress: (accessToken: string, id: string, patch: Partial<AddressWrite>) =>
    request<Address>(`/api/v1/store/addresses/${id}`, {
      method: "PUT",
      body: JSON.stringify(patch),
    }, accessToken),
  deleteAddress: (accessToken: string, id: string) =>
    request<void>(`/api/v1/store/addresses/${id}`, { method: "DELETE" }, accessToken),
  setDefaultAddress: (accessToken: string, id: string) =>
    request<Address>(`/api/v1/store/addresses/${id}/default`, { method: "POST" }, accessToken),
  checkout: (accessToken: string, address_id: string) =>
    request<Order>(`/api/v1/store/checkout`, {
      method: "POST",
      body: JSON.stringify({ address_id }),
    }, accessToken),
  listOrders: (accessToken: string) =>
    request<Order[]>(`/api/v1/store/orders`, {}, accessToken),
  getOrder: (accessToken: string, id: string) =>
    request<Order>(`/api/v1/store/orders/${id}`, {}, accessToken),
  cancelOrder: (accessToken: string, id: string) =>
    request<Order>(`/api/v1/store/orders/${id}/cancel`, { method: "POST" }, accessToken),
  initiatePayment: (accessToken: string, order_id: string, idempotency_key: string) =>
    request<PaymentInitiate>(`/api/v1/payments/initiate`, {
      method: "POST",
      body: JSON.stringify({ order_id, idempotency_key }),
    }, accessToken),
  getPayment: (accessToken: string, id: string) =>
    request<Payment>(`/api/v1/payments/${id}`, {}, accessToken),
  khataSummary: (accessToken: string) =>
    request<KhataSummary>(`/api/v1/khata/summary`, {}, accessToken),
  khataEntries: (accessToken: string, limit = 20, offset = 0) =>
    request<KhataEntriesPage>(`/api/v1/khata/entries?limit=${limit}&offset=${offset}`, {}, accessToken),
  // ── Step 16: suppliers ──
  listSuppliers: (accessToken: string, search?: string) => {
    const query = search ? `?search=${encodeURIComponent(search)}` : "";
    return request<Supplier[]>(`/api/v1/store/suppliers${query}`, {}, accessToken);
  },
  createSupplier: (accessToken: string, payload: SupplierWrite) =>
    request<Supplier>(`/api/v1/store/suppliers`, {
      method: "POST",
      body: JSON.stringify(payload),
    }, accessToken),
  getSupplier: (accessToken: string, id: string) =>
    request<Supplier>(`/api/v1/store/suppliers/${id}`, {}, accessToken),
  updateSupplier: (accessToken: string, id: string, patch: Partial<SupplierWrite>) =>
    request<Supplier>(`/api/v1/store/suppliers/${id}`, {
      method: "PUT",
      body: JSON.stringify(patch),
    }, accessToken),
  // ── Step 16: purchases ──
  listPurchases: (
    accessToken: string,
    filters: { supplier_id?: string; status?: string; from?: string; to?: string } = {},
  ) => {
    const params = new URLSearchParams();
    if (filters.supplier_id) params.set("supplier_id", filters.supplier_id);
    if (filters.status) params.set("status", filters.status);
    if (filters.from) params.set("from", filters.from);
    if (filters.to) params.set("to", filters.to);
    const query = params.toString();
    return request<Purchase[]>(`/api/v1/store/purchases${query ? `?${query}` : ""}`, {}, accessToken);
  },
  createPurchase: (accessToken: string, payload: PurchaseWrite) =>
    request<Purchase>(`/api/v1/store/purchases`, {
      method: "POST",
      body: JSON.stringify(payload),
    }, accessToken),
  getPurchase: (accessToken: string, id: string) =>
    request<Purchase>(`/api/v1/store/purchases/${id}`, {}, accessToken),
  updatePurchase: (accessToken: string, id: string, patch: Partial<PurchaseWrite>) =>
    request<Purchase>(`/api/v1/store/purchases/${id}`, {
      method: "PUT",
      body: JSON.stringify(patch),
    }, accessToken),
  addPurchaseItem: (accessToken: string, id: string, payload: PurchaseItemWrite) =>
    request<PurchaseItem>(`/api/v1/store/purchases/${id}/items`, {
      method: "POST",
      body: JSON.stringify(payload),
    }, accessToken),
  removePurchaseItem: (accessToken: string, id: string, itemId: string) =>
    request<void>(`/api/v1/store/purchases/${id}/items/${itemId}`, { method: "DELETE" }, accessToken),
  receivePurchase: (accessToken: string, id: string) =>
    request<Purchase & { duplicate?: boolean }>(`/api/v1/store/purchases/${id}/receive`, { method: "POST" }, accessToken),
  cancelPurchase: (accessToken: string, id: string) =>
    request<Purchase>(`/api/v1/store/purchases/${id}/cancel`, { method: "POST" }, accessToken),
  // ── Step 16: inventory ──
  listInventory: (
    accessToken: string,
    filters: { search?: string; status?: string; limit?: number; offset?: number } = {},
  ) => {
    const params = new URLSearchParams();
    if (filters.search) params.set("search", filters.search);
    if (filters.status) params.set("status", filters.status);
    if (filters.limit !== undefined) params.set("limit", String(filters.limit));
    if (filters.offset !== undefined) params.set("offset", String(filters.offset));
    const query = params.toString();
    return request<InventoryList>(`/api/v1/store/inventory${query ? `?${query}` : ""}`, {}, accessToken);
  },
  inventorySummary: (accessToken: string) =>
    request<InventorySummary>(`/api/v1/store/inventory/summary`, {}, accessToken),
  lowStock: (accessToken: string) =>
    request<InventoryItem[]>(`/api/v1/store/inventory/low-stock`, {}, accessToken),
  getInventory: (accessToken: string, variantId: string) =>
    request<InventoryDetail>(`/api/v1/store/inventory/${variantId}`, {}, accessToken),
  inventoryMovements: (
    accessToken: string,
    variantId: string,
    filters: { movement_type?: string; from?: string; to?: string; limit?: number; offset?: number } = {},
  ) => {
    const params = new URLSearchParams();
    if (filters.movement_type) params.set("movement_type", filters.movement_type);
    if (filters.from) params.set("from", filters.from);
    if (filters.to) params.set("to", filters.to);
    if (filters.limit !== undefined) params.set("limit", String(filters.limit));
    if (filters.offset !== undefined) params.set("offset", String(filters.offset));
    const query = params.toString();
    return request<MovementPage>(
      `/api/v1/store/inventory/${variantId}/movements${query ? `?${query}` : ""}`, {}, accessToken,
    );
  },
  adjustInventory: (
    accessToken: string,
    variantId: string,
    payload: { movement_type: string; quantity: string | number; reason?: string | null },
  ) =>
    request<StockMovement>(`/api/v1/store/inventory/${variantId}/adjust`, {
      method: "POST",
      body: JSON.stringify(payload),
    }, accessToken),
  // ── Step 17: staff (admin only; backend authoritative, 403 for non-admin) ──
  listStaff: async (accessToken: string): Promise<StaffMember[]> => {
    const body = await request<StaffMember[] | { staff: StaffMember[] }>(
      `/api/v1/store/staff`, {}, accessToken,
    );
    return Array.isArray(body) ? body : (body?.staff ?? []);
  },
  createStaff: (accessToken: string, payload: StaffCreate) =>
    request<StaffMember>(`/api/v1/store/staff`, {
      method: "POST",
      body: JSON.stringify(payload),
    }, accessToken),
  getStaff: (accessToken: string, id: string) =>
    request<StaffMember>(`/api/v1/store/staff/${id}`, {}, accessToken),
  updateStaff: (accessToken: string, id: string, patch: StaffUpdate) =>
    request<StaffMember>(`/api/v1/store/staff/${id}`, {
      method: "PUT",
      body: JSON.stringify(patch),
    }, accessToken),
  deactivateStaff: (accessToken: string, id: string) =>
    request<StaffMember>(`/api/v1/store/staff/${id}/deactivate`, { method: "POST" }, accessToken),
  activateStaff: (accessToken: string, id: string) =>
    request<StaffMember>(`/api/v1/store/staff/${id}/activate`, { method: "POST" }, accessToken),
  deleteStaff: (accessToken: string, id: string) =>
    request<{ active: boolean }>(`/api/v1/store/staff/${id}`, { method: "DELETE" }, accessToken),
  // ── Step 17: reorder level (admin + manager; staff 403) ──
  updateReorderLevel: (accessToken: string, variantId: string, payload: ReorderWrite) =>
    request<InventoryDetail>(`/api/v1/store/inventory/${variantId}/reorder-level`, {
      method: "PUT",
      body: JSON.stringify(payload),
    }, accessToken),
  // ── Step 18: staff orders (store-wide, read-only; staff roles only) ──
  listStaffOrders: (accessToken: string, limit = 50, offset = 0) =>
    request<Order[]>(`/api/v1/store/staff/orders?limit=${limit}&offset=${offset}`, {}, accessToken),
  getStaffOrder: (accessToken: string, id: string) =>
    request<Order>(`/api/v1/store/staff/orders/${id}`, {}, accessToken),
  staffOrderItems: (accessToken: string, id: string) =>
    request<OrderItem[]>(`/api/v1/store/staff/orders/${id}/items`, {}, accessToken),
  // ── Step 18: POS counter (staff roles; cancel = manager+) ──
  listPosProducts: async (
    accessToken: string,
    filters: { search?: string; limit?: number; offset?: number } = {},
  ): Promise<PosProduct[]> => {
    const params = new URLSearchParams();
    if (filters.search) params.set("search", filters.search);
    // Spec envelope carries limit/offset; the backend currently honours
    // search only and returns a bare array — extras are forwarded
    // harmlessly (FastAPI ignores undeclared query params).
    if (filters.limit !== undefined) params.set("limit", String(filters.limit));
    if (filters.offset !== undefined) params.set("offset", String(filters.offset));
    const query = params.toString();
    const raw = await request<PosProduct[] | PosProductPage>(
      `/api/v1/store/pos/products${query ? `?${query}` : ""}`, {}, accessToken,
    );
    return Array.isArray(raw) ? raw : (raw.items ?? []);
  },
  getPosProduct: (accessToken: string, variantId: string) =>
    request<PosProduct>(`/api/v1/store/pos/products/${variantId}`, {}, accessToken),
  createPosBill: (accessToken: string, payload: PosBillCreate) =>
    request<PosBill>(`/api/v1/store/pos/bills`, {
      method: "POST",
      body: JSON.stringify(payload),
    }, accessToken),
  listPosBills: (accessToken: string, filters: PosBillFilters = {}) => {
    const params = new URLSearchParams();
    if (filters.bill_number) params.set("bill_number", filters.bill_number);
    if (filters.customer_id) params.set("customer_id", filters.customer_id);
    if (filters.payment_mode) params.set("payment_mode", filters.payment_mode);
    if (filters.payment_status) params.set("payment_status", filters.payment_status);
    if (filters.sale_status) params.set("sale_status", filters.sale_status);
    if (filters.date_from) params.set("date_from", filters.date_from);
    if (filters.date_to) params.set("date_to", filters.date_to);
    params.set("limit", String(filters.limit ?? 20));
    params.set("offset", String(filters.offset ?? 0));
    return request<PosBillPage>(`/api/v1/store/pos/bills?${params.toString()}`, {}, accessToken);
  },
  getPosBill: (accessToken: string, id: string) =>
    request<PosBill>(`/api/v1/store/pos/bills/${id}`, {}, accessToken),
  completePosBill: (accessToken: string, id: string, payload: PosBillCompleteIn) =>
    request<PosBillCompleteOut>(`/api/v1/store/pos/bills/${id}/complete`, {
      method: "POST",
      body: JSON.stringify(payload),
    }, accessToken),
  cancelPosBill: (accessToken: string, id: string, reason?: string | null) =>
    request<PosBillCancelOut>(`/api/v1/store/pos/bills/${id}/cancel`, {
      method: "POST",
      body: JSON.stringify(reason && reason.trim() ? { reason: reason.trim() } : {}),
    }, accessToken),
  posReceipt: (accessToken: string, id: string) =>
    request<PosReceipt>(`/api/v1/store/pos/bills/${id}/receipt`, {}, accessToken),
  posSummary: (accessToken: string, day?: string) =>
    request<PosSummary>(
      `/api/v1/store/pos/summary${day ? `?day=${encodeURIComponent(day)}` : ""}`, {}, accessToken,
    ),
};
