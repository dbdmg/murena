#!/usr/bin/env python3
"""
Script di test semplice per verificare che solo gli agenti nel ranking vengano eseguiti.
"""

import sys
import os

# Add the backend directory to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

from app.services.llm.agents.ranking_agent import RankingAgent
from app.services.llm.agents.schema import RankingAgentResult, RankingOrder

# Test 1: Verifica che il ranking agent restituisca solo alcuni agenti
print("=" * 60)
print("TEST: Ranking Agent Output")
print("=" * 60)

query_test = "Cerca un'abitazione tra i 2500 e i 3000 m2 da riconvertire in studentato. L'abitazione deve essere vicino alla linea della Metropolitana."

ranking_agent = RankingAgent()
result = ranking_agent.run(query=query_test, mode="filtering")

print(f"\nQuery: {query_test}")
print(f"\nRanking Agent Result:")
print(f"  - Type: {type(result)}")

if hasattr(result, 'ranking') and result.ranking:
    ranking_list = result.ranking.ranking if hasattr(result.ranking, 'ranking') else result.ranking
    print(f"  - Active Agents: {ranking_list}")
    print(f"  - Number of Active Agents: {len(ranking_list)}")
    
    print("\n✅ SUCCESS: Il ranking agent ha restituito un sottoinsieme di agenti")
    print(f"   Gli agenti attivi sono: {', '.join(ranking_list)}")
    
    all_agents = ["location", "normative", "ape", "typology", "poi"]
    inactive = [a for a in all_agents if a not in ranking_list]
    if inactive:
        print(f"   Gli agenti INATTIVI dovrebbero essere: {', '.join(inactive)}")
    else:
        print("   Tutti gli agenti sono attivi in questo test")
else:
    print("  - ❌ ERRORE: Il ranking agent non ha restituito un ranking valido")
    
print("\n" + "=" * 60)
print("NOTA: Verifica nei log che gli agenti inattivi non vengano eseguiti")
print("=" * 60)
