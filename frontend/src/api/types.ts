/**
 * Application types, derived from the backend's OpenAPI document.
 *
 * `schema.d.ts` is generated — run `npm run generate:api` with the API up. Every
 * type below aliases a generated schema rather than restating it, so a backend
 * field that changes shape breaks `tsc` here instead of failing silently at
 * runtime. The aliases exist only to give the generated names a shorter, more
 * natural spelling at call sites.
 */
import type { components } from './schema'

type Schemas = components['schemas']

// --- Auth & orgs -----------------------------------------------------------

export type User = Schemas['UserRead']
export type TokenResponse = Schemas['TokenResponse']
export type MemberRole = Schemas['MemberRole']
export type Org = Schemas['OrgSummary']
export type Member = Schemas['MemberRead']
export type Invite = Schemas['InviteRead']
export type InviteCreated = Schemas['InviteCreated']

export const ROLE_RANK: Record<MemberRole, number> = { viewer: 1, admin: 2, owner: 3 }

/** Mirrors `MemberRole.covers` on the server — the server remains the authority. */
export function roleCovers(actual: MemberRole, required: MemberRole): boolean {
  return ROLE_RANK[actual] >= ROLE_RANK[required]
}

// --- Monitors --------------------------------------------------------------

export type Monitor = Schemas['MonitorRead']
export type MonitorStatus = Schemas['MonitorStatus']
export type Assertions = Schemas['Assertions']
export type MonitorInput = Schemas['MonitorCreate']
export type MonitorPatch = Schemas['MonitorUpdate']
export type CheckResult = Schemas['CheckResultRead']
export type CheckPage = Schemas['CheckPage']

/** Narrowed from the generated `MonitorCreate['method']`, which is optional. */
export type HttpMethod = NonNullable<Schemas['MonitorCreate']['method']>

export const INTERVAL_OPTIONS = [30, 60, 300, 900, 3600] as const

// --- Incidents -------------------------------------------------------------

export type Incident = Schemas['IncidentRead']
export type IncidentDetail = Schemas['IncidentDetail']
export type IncidentUpdate = Schemas['IncidentUpdateRead']
export type IncidentSeverity = Schemas['IncidentSeverity']

// --- Notification channels -------------------------------------------------

export type Channel = Schemas['ChannelRead']
export type ChannelType = Schemas['ChannelType']
export type ChannelTestResult = Schemas['ChannelTestResult']

// --- Status pages ----------------------------------------------------------

export type StatusPage = Schemas['StatusPageRead']
export type PublicStatusPage = Schemas['PublicStatusPage']
export type PublicMonitor = Schemas['PublicMonitor']
export type PublicDay = Schemas['PublicDay']
export type PublicIncident = Schemas['PublicIncident']
export type PublicIncidentUpdate = Schemas['PublicIncidentUpdate']

/** The overall/per-service banner state. */
export type PublicState = Schemas['PublicMonitor']['status']
/** One cell of the 90-day uptime bar. */
export type DayState = Schemas['PublicDay']['state']

// --- API keys --------------------------------------------------------------

export type ApiKey = Schemas['ApiKeyRead']
export type ApiKeyCreated = Schemas['ApiKeyCreated']
