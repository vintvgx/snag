// Base URL for the Flask backend (search/filter/notifications — never auth,
// that's Supabase's job on the client side). Defaults to localhost for the
// iOS simulator; a physical device needs your Mac's LAN IP until this is
// pointed at the deployed Railway URL.
const API_URL = process.env.EXPO_PUBLIC_API_URL ?? 'http://localhost:5001';

export type ListingAttrs = {
  year: number | string | null;
  trim: string | null;
  drivetrain: string | null;
  odometer: number | null;
  color: string | null;
};

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

export type Listing = {
  id: string;
  price: number;
  title: string;
  attrs: ListingAttrs;
  location: ListingLocation;
  url: string;
  seller_id: string;
  seller: SellerInfo;
};

export type SearchResponse = {
  source: string;
  count: number;
  listings: Listing[];
};

export type SearchFilters = {
  zip: string;
  range: number;
  year?: number;
  drivetrain?: 'RWD' | 'AWD';
};

export async function searchTeslaListings(filters: SearchFilters): Promise<SearchResponse> {
  const params = new URLSearchParams({
    zip: filters.zip,
    range: String(filters.range),
  });
  if (filters.year) {
    params.set('year_min', String(filters.year));
    params.set('year_max', String(filters.year));
  }
  if (filters.drivetrain) {
    params.set('drivetrain', filters.drivetrain);
  }

  const response = await fetch(`${API_URL}/search?${params.toString()}`);
  const body = await response.json();

  if (!response.ok) {
    throw new Error(body.detail ?? body.error ?? `Search failed (${response.status})`);
  }

  return body as SearchResponse;
}
