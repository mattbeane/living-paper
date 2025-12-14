#!/usr/bin/env python3
"""
Generate an HTML visualization of living paper claim-evidence relationships.
Shows claim health, evidence balance, and areas needing attention.
"""

import json
import sqlite3
from pathlib import Path
from collections import defaultdict

def get_db():
    db_path = Path(__file__).parent.parent / "analysis" / "living_paper" / "lp_public.sqlite"
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    return conn

def generate_html():
    db = get_db()

    # Get all claims with paper info
    claims = db.execute("""
        SELECT c.claim_id, c.paper_id, c.claim_type, c.text, c.confidence, c.status, c.verification_status
        FROM claim c
        ORDER BY c.paper_id, c.claim_id
    """).fetchall()

    # Methodological note: empirical claims = almost always quant ground truth
    # When qual contradicts quant, pause to ask what quant might be missing
    # theoretical claims = mechanisms, can be challenged by qual evidence

    # Get all links grouped by claim
    links = db.execute("""
        SELECT l.claim_id, l.evidence_id, l.relation, l.weight, l.note,
               e.summary, e.sensitivity_tier, e.evidence_type
        FROM claim_evidence_link l
        JOIN evidence e ON e.evidence_id = l.evidence_id
        ORDER BY l.claim_id, l.relation
    """).fetchall()

    # Group links by claim
    claim_links = defaultdict(list)
    for link in links:
        claim_links[link['claim_id']].append(dict(link))

    # Calculate health scores
    def calc_health(links_list):
        if not links_list:
            return 0, "no-evidence"

        supports = sum(1 for l in links_list if l['relation'] == 'supports')
        challenges = sum(1 for l in links_list if l['relation'] == 'challenges')
        qualifies = sum(1 for l in links_list if l['relation'] == 'qualifies')
        total = len(links_list)

        # Health = (supports - challenges) / total, scaled
        if challenges > supports:
            return -1, "challenged"
        elif challenges > 0 and challenges >= supports * 0.5:
            return 0.5, "contested"
        elif qualifies > supports:
            return 0.6, "qualified"
        elif supports > 0:
            return 1, "supported"
        else:
            return 0.3, "weak"

    # Group claims by paper
    papers = defaultdict(list)
    for claim in claims:
        c = dict(claim)
        c['links'] = claim_links.get(claim['claim_id'], [])
        c['health_score'], c['health_status'] = calc_health(c['links'])
        papers[claim['paper_id']].append(c)

    # Summary stats
    total_claims = len(claims)
    challenged = sum(1 for c in claims if calc_health(claim_links.get(c['claim_id'], []))[1] == 'challenged')
    contested = sum(1 for c in claims if calc_health(claim_links.get(c['claim_id'], []))[1] == 'contested')
    supported = sum(1 for c in claims if calc_health(claim_links.get(c['claim_id'], []))[1] == 'supported')

    # Generate HTML
    html = f"""<!DOCTYPE html>
<html>
<head>
    <title>Living Paper Verification Dashboard</title>
    <style>
        * {{ box-sizing: border-box; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            max-width: 1200px;
            margin: 0 auto;
            padding: 20px;
            background: #f5f5f5;
        }}
        h1 {{ color: #333; margin-bottom: 10px; }}
        .summary {{
            display: flex;
            gap: 20px;
            margin-bottom: 30px;
            flex-wrap: wrap;
        }}
        .stat-box {{
            background: white;
            padding: 20px;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            min-width: 150px;
        }}
        .stat-box .number {{ font-size: 36px; font-weight: bold; }}
        .stat-box .label {{ color: #666; font-size: 14px; }}
        .stat-box.red .number {{ color: #d32f2f; }}
        .stat-box.yellow .number {{ color: #f57c00; }}
        .stat-box.green .number {{ color: #388e3c; }}

        .paper-section {{
            background: white;
            margin-bottom: 20px;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            overflow: hidden;
        }}
        .paper-header {{
            background: #1976d2;
            color: white;
            padding: 15px 20px;
            font-size: 18px;
            font-weight: 600;
        }}
        .claim {{
            border-bottom: 1px solid #eee;
            padding: 15px 20px;
        }}
        .claim:last-child {{ border-bottom: none; }}
        .claim-header {{
            display: flex;
            align-items: flex-start;
            gap: 12px;
        }}
        .health-indicator {{
            width: 12px;
            height: 12px;
            border-radius: 50%;
            margin-top: 5px;
            flex-shrink: 0;
        }}
        .health-supported {{ background: #4caf50; }}
        .health-qualified {{ background: #8bc34a; }}
        .health-contested {{ background: #ff9800; }}
        .health-challenged {{ background: #f44336; }}
        .health-weak {{ background: #9e9e9e; }}
        .health-no-evidence {{ background: #e0e0e0; }}

        .claim-text {{
            flex-grow: 1;
            font-size: 15px;
            line-height: 1.4;
        }}
        .claim-id {{
            font-family: monospace;
            font-size: 12px;
            color: #666;
            background: #f0f0f0;
            padding: 2px 6px;
            border-radius: 3px;
        }}
        .confidence {{
            font-size: 12px;
            color: #666;
            margin-left: 8px;
        }}
        .claim-type {{
            font-size: 10px;
            padding: 2px 6px;
            border-radius: 3px;
            margin-left: 8px;
            font-weight: 500;
        }}
        .claim-type.empirical {{ background: #e8f5e9; color: #2e7d32; }}
        .claim-type.theoretical {{ background: #fff3e0; color: #e65100; }}
        .claim-type.methodological {{ background: #e3f2fd; color: #1565c0; }}
        .claim-meta {{
            display: flex;
            align-items: center;
            margin-bottom: 6px;
        }}

        .evidence-list {{
            margin-top: 10px;
            padding-left: 24px;
        }}
        .evidence-item {{
            font-size: 13px;
            padding: 6px 10px;
            margin: 4px 0;
            border-radius: 4px;
            display: flex;
            gap: 8px;
        }}
        .evidence-item.supports {{ background: #e8f5e9; border-left: 3px solid #4caf50; }}
        .evidence-item.challenges {{ background: #ffebee; border-left: 3px solid #f44336; }}
        .evidence-item.qualifies {{ background: #fff3e0; border-left: 3px solid #ff9800; }}
        .evidence-item.illustrates {{ background: #e3f2fd; border-left: 3px solid #2196f3; }}
        .evidence-item.necessitates {{ background: #f3e5f5; border-left: 3px solid #9c27b0; }}

        .relation-tag {{
            font-size: 11px;
            font-weight: 600;
            text-transform: uppercase;
            min-width: 70px;
        }}
        .evidence-summary {{
            color: #333;
            flex-grow: 1;
        }}
        .evidence-tier {{
            font-size: 10px;
            color: #999;
            padding: 1px 4px;
            background: #f0f0f0;
            border-radius: 2px;
        }}
        .evidence-tier.controlled {{ background: #fff3e0; color: #e65100; }}

        .legend {{
            display: flex;
            gap: 20px;
            margin-bottom: 20px;
            flex-wrap: wrap;
        }}
        .legend-item {{
            display: flex;
            align-items: center;
            gap: 6px;
            font-size: 13px;
            color: #666;
        }}

        .paper-stats {{
            font-size: 13px;
            color: rgba(255,255,255,0.8);
            margin-top: 4px;
        }}

        details {{ cursor: pointer; }}
        details summary {{ outline: none; }}
        details summary::-webkit-details-marker {{ display: none; }}
    </style>
</head>
<body>
    <h1>Living Paper Verification Dashboard</h1>
    <p style="color: #666; margin-bottom: 20px;">Claim-evidence traceability across your research papers</p>

    <div class="summary">
        <div class="stat-box">
            <div class="number">{total_claims}</div>
            <div class="label">Total Claims</div>
        </div>
        <div class="stat-box green">
            <div class="number">{supported}</div>
            <div class="label">Well Supported</div>
        </div>
        <div class="stat-box yellow">
            <div class="number">{contested}</div>
            <div class="label">Contested</div>
        </div>
        <div class="stat-box red">
            <div class="number">{challenged}</div>
            <div class="label">Challenged</div>
        </div>
    </div>

    <div class="legend">
        <div class="legend-item"><div class="health-indicator health-supported"></div> Supported</div>
        <div class="legend-item"><div class="health-indicator health-qualified"></div> Qualified</div>
        <div class="legend-item"><div class="health-indicator health-contested"></div> Contested</div>
        <div class="legend-item"><div class="health-indicator health-challenged"></div> Challenged</div>
        <div class="legend-item"><div class="health-indicator health-weak"></div> Weak evidence</div>
    </div>

    <div style="background: #e3f2fd; padding: 12px 16px; border-radius: 6px; margin-bottom: 20px; font-size: 13px; color: #1565c0;">
        <strong>Methodological note:</strong> Empirical claims (quant) are almost always ground truth—but when qual contradicts quant, pause and ask what the quant might be missing.
        Usually, qual perceptions are mistaken beliefs (a finding in itself). Occasionally, qual reveals gaps in the quantitative record.
        Theoretical claims (mechanisms) can be challenged by qual, but quant behavioral patterns can rule out mechanisms.
    </div>
"""

    # Paper name mapping - will use paper_id as fallback if not mapped
    paper_names = {}

    for paper_id, paper_claims in papers.items():
        supports_count = sum(1 for c in paper_claims if c['health_status'] == 'supported')
        challenges_count = sum(1 for c in paper_claims if c['health_status'] in ('challenged', 'contested'))

        html += f"""
    <div class="paper-section">
        <div class="paper-header">
            {paper_names.get(paper_id, paper_id)}
            <div class="paper-stats">{len(paper_claims)} claims · {supports_count} supported · {challenges_count} need attention</div>
        </div>
"""
        for claim in paper_claims:
            health_class = f"health-{claim['health_status']}"
            conf_pct = int(claim['confidence'] * 100)
            claim_type = claim['claim_type']
            type_label = "QUANT" if claim_type == "empirical" else "MECHANISM" if claim_type == "theoretical" else claim_type.upper()

            html += f"""
        <div class="claim">
            <div class="claim-header">
                <div class="health-indicator {health_class}" title="{claim['health_status']}"></div>
                <div class="claim-text">
                    <div class="claim-meta">
                        <span class="claim-id">{claim['claim_id']}</span>
                        <span class="claim-type {claim_type}">{type_label}</span>
                        <span class="confidence">{conf_pct}% confidence</span>
                    </div>
                    <details>
                        <summary>{claim['text']}</summary>
                        <div class="evidence-list">
"""
            if claim['links']:
                for link in claim['links']:
                    tier_class = "controlled" if link['sensitivity_tier'] == 'CONTROLLED' else ""
                    summary = "[CONTROLLED]" if link['sensitivity_tier'] == 'CONTROLLED' else link['summary'][:100]
                    html += f"""
                            <div class="evidence-item {link['relation']}">
                                <span class="relation-tag">{link['relation']}</span>
                                <span class="evidence-summary">{summary}</span>
                                <span class="evidence-tier {tier_class}">{link['sensitivity_tier']}</span>
                            </div>
"""
            else:
                html += """
                            <div class="evidence-item" style="background: #fafafa; border-left: 3px solid #ccc;">
                                <span style="color: #999;">No evidence linked</span>
                            </div>
"""
            html += """
                        </div>
                    </details>
                </div>
            </div>
        </div>
"""
        html += """
    </div>
"""

    html += """
    <p style="color: #999; font-size: 12px; margin-top: 30px; text-align: center;">
        Generated by living_paper verification system
    </p>
</body>
</html>
"""
    return html

if __name__ == "__main__":
    import sys
    out_path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).parent.parent / "analysis" / "living_paper" / "dashboard.html"
    out_path.write_text(generate_html())
    print(f"Dashboard written to {out_path}")
