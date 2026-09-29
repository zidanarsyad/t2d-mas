import { ArrowDownRight, ArrowUpRight } from "lucide-react";

export function Eyebrow({children}) { return <p className="eyebrow">{children}</p>; }
export function Panel({children,className=""}) { return <section className={`panel ${className}`}>{children}</section>; }
export function Heading({eyebrow,title,subtitle,action}) { return <div className="page-heading"><div><Eyebrow>{eyebrow}</Eyebrow><h1>{title}</h1><p>{subtitle}</p></div>{action}</div>; }
export function Severity({value}) { return <span className={`severity sev-${value.toLowerCase()}`}><i aria-hidden="true"/>{value}</span>; }
export function Tag({children,tone="neutral"}) { return <span className={`tag tag-${tone}`}>{children}</span>; }
export function Metric({label,value,change,note,icon:Icon,good=true}) { return <Panel className="metric"><div className="metric-label">{label}<span><Icon size={15}/></span></div><strong>{value}</strong><div className="metric-foot"><b className={good?"positive":"negative"}>{good?<ArrowDownRight size={13}/>:<ArrowUpRight size={13}/>} {change}</b><small>{note}</small></div></Panel>; }
export function SectionTitle({title,detail,action}) { return <div className="section-title"><div><h2>{title}</h2>{detail&&<p>{detail}</p>}</div>{action}</div>; }
