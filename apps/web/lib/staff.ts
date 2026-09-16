/**
 * Step 17 staff display helpers (shared, non-page module).
 * Next.js page files may only export route exports — helpers live here.
 */
import type { StaffMember } from "./api";

export function staffRoleLabel(role: string): string {
  if (role === "admin") return "प्रशासक Admin";
  if (role === "store_manager") return "दुकान व्यवस्थापक Store Manager";
  if (role === "store_staff") return "दुकान कर्मचारी Store Staff";
  return role;
}

export function staffMobile(s: StaffMember): string {
  return s.mobile ?? s.mobile_number ?? "—";
}
