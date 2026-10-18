import type { ReactNode } from "react";
import { Link } from "react-router-dom";

export function LoadingState({ label = "Loading DevFlow…" }: { label?: string }) { return <div className="state-card"><span className="spinner" />{label}</div>; }
export function EmptyState({ title, detail }: { title: string; detail: string }) { return <div className="state-card"><div className="empty-icon">∅</div><strong>{title}</strong><span>{detail}</span></div>; }
export function ErrorState({ message, onRetry }: { message: string; onRetry?: () => void }) { return <div className="state-card error-state" role="alert"><span className="state-icon">!</span><strong>{message}</strong><span>Check the connection and try again.</span>{onRetry && <button className="secondary-button" onClick={onRetry}>Retry</button>}</div>; }
export function Badge({ children, tone = "neutral" }: { children: ReactNode; tone?: "neutral" | "good" | "warn" | "bad" | "accent" }) { return <span className={`badge badge-${tone}`}>{children}</span>; }
export function Card({ children, className = "" }: { children: ReactNode; className?: string }) { return <section className={`card ${className}`}>{children}</section>; }
export function PageTitle({ eyebrow, title, detail, action }: { eyebrow?: string; title: string; detail?: string; action?: ReactNode }) { return <div className="page-title"><div>{eyebrow && <div className="eyebrow">{eyebrow}</div>}<h1>{title}</h1>{detail && <p>{detail}</p>}</div>{action}</div>; }
export function Metric({ label, value, accent = false }: { label: string; value: string | number; accent?: boolean }) { return <div className={`metric ${accent ? "metric-accent" : ""}`}><span>{label}</span><strong>{value}</strong></div>; }
export function SectionLabel({ children, detail }: { children: ReactNode; detail?: string }) { return <div className="section-label"><span>{children}</span>{detail && <small>{detail}</small>}</div>; }
export function EmptyAction({ title, detail, to, label }: { title: string; detail: string; to?: string; label?: string }) { return <div className="state-card"><div className="empty-icon">∅</div><strong>{title}</strong><span>{detail}</span>{to && label && <Link className="secondary-button" to={to}>{label}</Link>}</div>; }
