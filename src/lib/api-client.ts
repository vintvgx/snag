// Base URL for the Flask backend (search/filter/notifications — never auth,
// that's Supabase's job on the client side). Defaults to localhost for the
// iOS simulator; a physical device needs your Mac's LAN IP until this is
// pointed at the deployed Railway URL.
const API_URL = process.env.EXPO_PUBLIC_API_URL ?? 'http://localhost:5001';

// Temporary: eBay/Amazon PA-API access is still pending approval (see
// docs/search-and-tracking-design.md), so search is pinned to the one
// source that's actually configured right now instead of the full
// eBay+Amazon+Google fan-out. Remove this default (or pass `source`
// explicitly per call) once eBay/Amazon land — /search does the full
// unified fan-out whenever no `source` param is given.
const DEFAULT_SOURCE = 'google';

export type ListingAttrs = Record<string, string | number | boolean | null | undefined>;

export type ListingLocation = {
  city: string | null;
  state: string | null;
  zip: string | null;
};

export type SellerInfo = {
  is_official_source: boolean;
  display_name: string | null;
  rating: number | null;
  review_count: number | null;
  sale_count: number | null;
};

export type ListingSource = 'tesla' | 'ebay' | 'amazon' | 'google' | 'web';

export type Listing = {
  id: string;
  source: ListingSource;
  price: number;
  title: string;
  attrs: ListingAttrs;
  location: ListingLocation;
  url: string;
  seller_id: string | null;
  seller: SellerInfo;
};

// 'ok' | 'timeout' | 'unavailable: <reason>' | 'schema_drift: <reason>' | 'No adapter registered for source ...'
export type SourceStatus = string;

export type SearchResponse = {
  query: string;
  cached: boolean;
  last_searched_at: string;
  sources_status: Record<string, SourceStatus>;
  count: number;
  listings: Listing[];
};

export async function searchListings(
  query: string,
  opts?: { source?: string; fresh?: boolean }
): Promise<SearchResponse> {
  const params = new URLSearchParams({
    q: query,
    source: opts?.source ?? DEFAULT_SOURCE,
  });
  if (opts?.fresh) {
    params.set('fresh', '1');
  }

  const response = await fetch(`${API_URL}/search?${params.toString()}`);
  const body = await response.json();

  if (!response.ok) {
    throw new Error(body.detail ?? body.error ?? `Search failed (${response.status})`);
  }

  return body as SearchResponse;
}
