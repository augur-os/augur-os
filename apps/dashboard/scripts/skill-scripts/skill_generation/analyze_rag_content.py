#!/usr/bin/env python3
"""
Content Analysis Service

Analyzes indexed RAG content to understand domain, patterns, use cases, and Five Pillar mapping.
"""
# TODO_CLEANUP: This file is 930 lines — consider splitting into smaller modules

import json
import sys
import re
from pathlib import Path
from typing import Any, Dict, List
from collections import Counter


def _out(*args: object, **kwargs: object) -> None:
    sep = kwargs.get("sep", " ")
    end = kwargs.get("end", "\n")
    file = kwargs.get("file", sys.stdout)
    file.write(sep.join(str(arg) for arg in args) + str(end))


# Add repo root to path
repo_root = Path(__file__).resolve().parents[5]
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))

# Import RAG query service
try:
    # Try multiple import paths
    try:
        from plugins.horizontal.memory.local_rag.services.search_service import DocumentSearcher
    except ImportError:
        # Try relative import
        from horizontal.memory.local_rag.services.search_service import DocumentSearcher
    RAG_AVAILABLE = True
except ImportError as e:
    RAG_AVAILABLE = False
    _out(f"Warning: RAG search service not available: {e}. Using placeholder data.", file=sys.stderr)


# Domain keywords for classification
DOMAIN_KEYWORDS = {
    'interior-design': [
        'interior',
        'design',
        'furniture',
        'decor',
        'decoration',
        'space',
        'room',
        'kitchen',
        'bathroom',
        'living',
        'bedroom',
        'apartment',
        'home',
        'residential',
        'commercial',
        'architectural',
        'plan',
        'layout',
        'style',
        'color',
        'material',
        'finish',
        'cabinet',
        'countertop',
        'tile',
        'flooring',
        'lighting',
        'fixture',
        'appliance',
        'client',
        'project',
        'consultation',
        'questionnaire',
        'quote',
        'estimate',
        'renovation',
        'remodel',
        'construction',
        'blueprint',
        'cad',
        'drawing',
    ],
    'design': [
        'design',
        'creative',
        'visual',
        'aesthetic',
        'style',
        'brand',
        'graphic',
        'logo',
        'layout',
        'typography',
        'color',
        'palette',
        'concept',
        'mood',
        'board',
    ],
    'medical': [
        'medical',
        'health',
        'symptom',
        'diagnosis',
        'treatment',
        'doctor',
        'patient',
        'medication',
        'lab',
        'test',
        'clinical',
        'hospital',
        'disease',
        'condition',
    ],
    'legal': [
        'contract',
        'agreement',
        'legal',
        'law',
        'clause',
        'party',
        'term',
        'provision',
        'liability',
        'jurisdiction',
        'confidential',
        'non-disclosure',
        'attorney',
    ],
    'financial': [
        'financial',
        'investment',
        'portfolio',
        'stock',
        'revenue',
        'expense',
        'profit',
        'loss',
        'balance',
        'asset',
        'liability',
        'budget',
    ],
    'research': [
        'research',
        'study',
        'analysis',
        'data',
        'hypothesis',
        'methodology',
        'conclusion',
        'experiment',
        'paper',
        'citation',
        'reference',
    ],
    'technical': [
        'technical',
        'api',
        'code',
        'function',
        'class',
        'implementation',
        'architecture',
        'system',
        'database',
        'server',
        'client',
    ],
}


def _query_rag(rag_project_id: str, query: str, k: int = 10, searcher: Any = None) -> List[dict]:
    """
    Query RAG system for documents.

    Args:
        rag_project_id: RAG project ID
        query: Search query
        k: Number of results
        searcher: Optional pre-initialized DocumentSearcher instance

    Returns:
        List of search results
    """
    if not RAG_AVAILABLE:
        return []

    try:
        # Initialize searcher if not provided
        if searcher is None:
            user_data_dir = Path.home() / 'Projects' / 'augur' / 'local-rag' / 'projects' / rag_project_id
            searcher = DocumentSearcher(user_data_dir=str(user_data_dir))

        results = searcher.search(query, k=k)
        return results
    except Exception as e:
        _out(f"Error querying RAG: {e}", file=sys.stderr)
        return []


def identify_domain(rag_project_id: str, searcher: Any = None) -> Dict[str, Any]:
    """
    Identify knowledge domain from RAG content.

    Args:
        rag_project_id: RAG project ID
        searcher: Optional DocumentSearcher instance

    Returns:
        Domain identification result with domain name, role, confidence
    """
    # Query RAG for representative content
    queries = ["What is this document about?", "Main topics and subjects", "Key concepts and terminology"]

    all_text = []
    for query in queries:
        results = _query_rag(rag_project_id, query, k=5, searcher=searcher)
        all_text.extend([r.get('preview', '') for r in results])

    if not all_text:
        # Fallback if RAG not available
        return {
            'primary': 'general',
            'secondary': [],
            'confidence': 0.5,
            'role': 'knowledge-assistant',
            'role_description': 'General knowledge assistant',
        }

    # Combine all text for analysis
    combined_text = ' '.join(all_text).lower()

    # Count domain keyword matches
    domain_scores = {}
    for domain, keywords in DOMAIN_KEYWORDS.items():
        score = sum(1 for keyword in keywords if keyword in combined_text)
        domain_scores[domain] = score

    # Identify primary domain (highest score)
    if domain_scores:
        primary_domain = max(domain_scores, key=domain_scores.get)
        max_score = domain_scores[primary_domain]

        # Calculate confidence based on score distribution
        total_keywords = sum(domain_scores.values())
        confidence = min(max_score / max(total_keywords, 1) * 1.5, 0.95) if total_keywords > 0 else 0.5

        # Find secondary domains
        secondary = [d for d, s in domain_scores.items() if d != primary_domain and s > max_score * 0.3]
    else:
        primary_domain = 'general'
        confidence = 0.5
        secondary = []

    # Generate role based on domain
    role_map = {
        'medical': 'virtual-doctor',
        'legal': 'contract-analyzer',
        'financial': 'financial-advisor',
        'research': 'research-assistant',
        'technical': 'technical-assistant',
        'general': 'knowledge-assistant',
    }

    role = role_map.get(primary_domain, 'knowledge-assistant')

    # Generate role description
    role_descriptions = {
        'medical': 'Personal health assistant for tracking symptoms and medical history',
        'legal': 'Legal contract analysis and comparison tool',
        'financial': 'Financial analysis and portfolio management assistant',
        'research': 'Research paper analysis and citation management tool',
        'technical': 'Technical documentation and code analysis assistant',
        'general': 'General knowledge management and retrieval assistant',
    }

    return {
        'primary': primary_domain,
        'secondary': secondary,
        'confidence': round(confidence, 2),
        'role': role,
        'role_description': role_descriptions.get(primary_domain, role_descriptions['general']),
    }


def map_to_pillars(rag_project_id: str, domain: str, searcher: Any = None) -> Dict[str, Any]:
    """
    Map content to Five Pillar Framework.

    Args:
        rag_project_id: RAG project ID
        domain: Identified domain
        searcher: Optional DocumentSearcher instance

    Returns:
        Pillar mapping with relevance scores and suggested MCP tools
    """
    # Query RAG for different aspects
    queries = {
        'temporal': "dates times chronological order timeline",
        'quantitative': "numbers data metrics measurements values",
        'entities': "names people organizations locations",
        'actions': "tasks actions steps procedures processes",
    }

    results = {}
    for key, query in queries.items():
        results[key] = _query_rag(rag_project_id, query, k=3, searcher=searcher)

    # Analyze for temporal patterns (Capture pillar)
    temporal_content = ' '.join([r.get('preview', '') for r in results['temporal']])
    has_dates = bool(re.search(r'\d{4}[-/]\d{1,2}[-/]\d{1,2}|\d{1,2}/\d{1,2}/\d{4}', temporal_content))
    has_tracking = any(word in temporal_content.lower() for word in ['log', 'record', 'track', 'capture', 'entry'])

    capture_relevance = 0.7 if has_dates or has_tracking else 0.4

    # Analyze for quantitative data (Analyze pillar)
    quant_content = ' '.join([r.get('preview', '') for r in results['quantitative']])
    has_numbers = bool(re.search(r'\d+\.\d+|\d+%|\$\d+', quant_content))
    has_analysis_terms = any(
        word in quant_content.lower() for word in ['analysis', 'trend', 'pattern', 'correlation', 'compare']
    )

    analyze_relevance = 0.85 if has_numbers or has_analysis_terms else 0.6

    # Analyze for action items (Execute pillar)
    action_content = ' '.join([r.get('preview', '') for r in results['actions']])
    has_actions = any(
        word in action_content.lower() for word in ['generate', 'create', 'export', 'send', 'execute', 'perform']
    )

    execute_relevance = 0.75 if has_actions else 0.5

    # Grow depends on whether content suggests learning
    grow_keywords = ['learn', 'adapt', 'improve', 'update', 'refine']
    has_growth = any(keyword in action_content.lower() for keyword in grow_keywords)
    grow_relevance = 0.65 if has_growth else 0.4

    # Generate domain-specific MCP tool suggestions
    tool_suggestions = _generate_tool_suggestions(domain)

    return {
        'capture': {
            'relevance': round(capture_relevance, 2),
            'reasoning': 'Temporal patterns detected' if has_dates else 'Limited temporal data',
            'suggested_capabilities': tool_suggestions['capture']['capabilities'],
            'suggested_mcp_tools': tool_suggestions['capture']['tools'],
        },
        'analyze': {
            'relevance': round(analyze_relevance, 2),
            'reasoning': 'Quantitative data and analysis terms found' if has_numbers else 'Some analytical content',
            'suggested_capabilities': tool_suggestions['analyze']['capabilities'],
            'suggested_mcp_tools': tool_suggestions['analyze']['tools'],
        },
        'execute': {
            'relevance': round(execute_relevance, 2),
            'reasoning': 'Action-oriented content detected' if has_actions else 'Some executable tasks',
            'suggested_capabilities': tool_suggestions['execute']['capabilities'],
            'suggested_mcp_tools': tool_suggestions['execute']['tools'],
        },
        'recall': {
            'relevance': 1.0,
            'reasoning': 'Always included for RAG-based knowledge retrieval',
            'suggested_capabilities': tool_suggestions['recall']['capabilities'],
            'suggested_mcp_tools': tool_suggestions['recall']['tools'],
        },
        'grow': {
            'relevance': round(grow_relevance, 2),
            'reasoning': 'Learning patterns detected' if has_growth else 'Limited growth potential',
            'suggested_capabilities': tool_suggestions['grow']['capabilities'],
            'suggested_mcp_tools': tool_suggestions['grow']['tools'],
        },
    }


def _generate_tool_suggestions(domain: str) -> Dict[str, Any]:
    """Generate domain-specific tool suggestions for each pillar."""

    domain_tools = {
        'medical': {
            'capture': {
                'capabilities': ['Record symptoms', 'Log medications', 'Track vital signs'],
                'tools': ['capture_symptom', 'capture_medication', 'capture_vital'],
            },
            'analyze': {
                'capabilities': ['Analyze trends', 'Correlate symptoms', 'Assess risk'],
                'tools': ['analyze_trends', 'analyze_correlations', 'analyze_risk'],
            },
            'execute': {
                'capabilities': ['Generate treatment plan', 'Create reminders'],
                'tools': ['execute_treatment_plan', 'execute_reminders'],
            },
            'recall': {
                'capabilities': ['Search medical history', 'Find similar cases'],
                'tools': ['recall_history', 'recall_similar'],
            },
            'grow': {'capabilities': ['Learn from diagnoses'], 'tools': ['grow_knowledge']},
        },
        'legal': {
            'capture': {'capabilities': ['Upload contracts'], 'tools': ['capture_contract']},
            'analyze': {
                'capabilities': ['Extract terms', 'Compare clauses', 'Assess risk'],
                'tools': ['analyze_terms', 'analyze_compare', 'analyze_risk'],
            },
            'execute': {
                'capabilities': ['Generate summary', 'Export term sheet'],
                'tools': ['execute_summary', 'execute_export'],
            },
            'recall': {
                'capabilities': ['Search clauses', 'Find precedents'],
                'tools': ['recall_clauses', 'recall_precedents'],
            },
            'grow': {'capabilities': ['Learn contract patterns'], 'tools': ['grow_patterns']},
        },
    }

    # Default/general tools
    default_tools = {
        'capture': {'capabilities': ['Capture new data'], 'tools': ['capture_data']},
        'analyze': {
            'capabilities': ['Analyze patterns', 'Generate insights'],
            'tools': ['analyze_patterns', 'analyze_insights'],
        },
        'execute': {
            'capabilities': ['Execute actions', 'Generate reports'],
            'tools': ['execute_action', 'execute_report'],
        },
        'recall': {'capabilities': ['Search knowledge', 'Find similar'], 'tools': ['recall_search', 'recall_similar']},
        'grow': {'capabilities': ['Learn from data'], 'tools': ['grow_learn']},
    }

    return domain_tools.get(domain, default_tools)


def detect_patterns(rag_project_id: str, searcher: Any = None) -> List[Dict[str, Any]]:
    """
    Detect structural and content patterns.

    Args:
        rag_project_id: RAG project ID
        searcher: Optional DocumentSearcher instance

    Returns:
        Dict with structural and content patterns
    """
    # Query for structural patterns
    results = _query_rag(rag_project_id, "structure format organization", k=5, searcher=searcher)

    if not results:
        return {'structural': [{'type': 'database', 'confidence': 0.5}], 'content': []}

    combined_text = ' '.join([r.get('preview', '') for r in results]).lower()

    structural_patterns = []

    # Check for chronological patterns
    if re.search(r'\d{4}[-/]\d{1,2}[-/]\d{1,2}', combined_text):
        structural_patterns.append(
            {'type': 'chronological', 'confidence': 0.8, 'description': 'Time-series entries detected'}
        )

    # Check for numbered sections (hierarchical)
    if re.search(r'\n\s*\d+\.\d+|\n\s*[A-Z]\.|section \d+', combined_text, re.IGNORECASE):
        structural_patterns.append(
            {'type': 'hierarchical', 'confidence': 0.75, 'description': 'Numbered sections and hierarchy'}
        )

    # Check for forms/tables
    if any(term in combined_text for term in ['table', 'column', 'row', 'field', 'form']):
        structural_patterns.append(
            {'type': 'structured_forms', 'confidence': 0.7, 'description': 'Structured forms or tables'}
        )

    # Default to database pattern if no specific pattern found
    if not structural_patterns:
        structural_patterns.append({'type': 'database', 'confidence': 0.6, 'description': 'General database structure'})

    # Detect content patterns
    content_patterns = []

    # Check for recurring entities
    entities = re.findall(r'\b[A-Z][a-z]+(?: [A-Z][a-z]+)*\b', combined_text)
    if entities:
        entity_counts = Counter(entities)
        common_entities = [e for e, c in entity_counts.most_common(5)]
        content_patterns.append({'type': 'recurring_entities', 'examples': common_entities})

    return {'structural': structural_patterns, 'content': content_patterns}


def infer_use_cases(rag_project_id: str, domain: str, pillars: Dict[str, Any]) -> List[str]:
    """
    Infer domain-specific use cases.

    Args:
        rag_project_id: RAG project ID
        domain: Identified domain
        pillars: Pillar mapping

    Returns:
        List of use cases
    """
    use_cases = []

    # Always include recall use case
    use_cases.append(f"Search {domain} knowledge base")

    # Add use cases based on relevant pillars
    for pillar, data in pillars.items():
        if pillar == 'recall':
            continue  # Already added

        relevance = data.get('relevance', 0)
        if relevance > 0.6:
            capabilities = data.get('suggested_capabilities', [])
            use_cases.extend(capabilities[:2])  # Add top 2 capabilities

    return use_cases[:6]  # Limit to 6 use cases


def extract_metadata(rag_project_id: str, searcher: Any = None) -> Dict[str, Any]:
    """
    Extract key metadata from content.

    Args:
        rag_project_id: RAG project ID
        searcher: Optional DocumentSearcher instance

    Returns:
        Metadata dict with topics, entities, dates, etc.
    """
    # Query for metadata
    results = _query_rag(rag_project_id, "summary overview main points", k=10, searcher=searcher)

    if not results:
        return {'entities': [], 'date_range': None, 'primary_topics': [], 'total_chunks': 0}

    combined_text = ' '.join([r.get('preview', '') for r in results])

    # Extract dates
    dates = re.findall(r'\d{4}[-/]\d{1,2}[-/]\d{1,2}', combined_text)
    date_range = f"{min(dates)} to {max(dates)}" if dates else None

    # Extract entities (capitalized words/phrases)
    entities = re.findall(r'\b[A-Z][a-z]+(?: [A-Z][a-z]+)*\b', combined_text)
    entity_counts = Counter(entities)
    top_entities = [e for e, c in entity_counts.most_common(10)]

    # Extract topics (frequent non-entity words)
    words = re.findall(r'\b[a-z]{4,}\b', combined_text.lower())
    word_counts = Counter(words)
    # Filter out common words
    stopwords = {'that', 'this', 'with', 'from', 'have', 'been', 'were', 'will', 'would', 'should'}
    topics = [w for w, c in word_counts.most_common(20) if w not in stopwords][:10]

    # Get total chunks from results metadata
    total_chunks = len(results)

    return {'entities': top_entities, 'date_range': date_range, 'primary_topics': topics, 'total_chunks': total_chunks}


def analyze_business_opportunities(rag_project_id: str, domain: str, searcher: Any = None) -> Dict[str, Any]:
    """
    Analyze business opportunities from content.

    Args:
        rag_project_id: RAG project ID
        domain: Identified domain
        searcher: Optional DocumentSearcher instance

    Returns:
        Business opportunities analysis
    """
    # Business-focused queries
    business_queries = [
        "What services or products does this business offer?",
        "What are the main business processes and workflows?",
        "What customer interactions and touchpoints exist?",
        "What documents, forms, or templates are used?",
        "What project management or tracking activities happen?",
        "What are common pain points or challenges?",
        "What data needs to be tracked or managed?",
        "What repetitive tasks or manual processes exist?",
    ]

    business_insights = {}
    all_content = []

    for query in business_queries:
        results = _query_rag(rag_project_id, query, k=5, searcher=searcher)
        content = ' '.join([r.get('preview', '') for r in results])
        all_content.append(content)

        # Extract key insights
        if 'service' in query.lower() or 'product' in query.lower():
            business_insights['services'] = content[:500]
        elif 'process' in query.lower() or 'workflow' in query.lower():
            business_insights['processes'] = content[:500]
        elif 'customer' in query.lower() or 'interaction' in query.lower():
            business_insights['customer_interactions'] = content[:500]
        elif 'document' in query.lower() or 'form' in query.lower():
            business_insights['documents'] = content[:500]
        elif 'project' in query.lower() or 'tracking' in query.lower():
            business_insights['project_management'] = content[:500]
        elif 'pain' in query.lower() or 'challenge' in query.lower():
            business_insights['pain_points'] = content[:500]
        elif 'data' in query.lower() or 'track' in query.lower():
            business_insights['data_needs'] = content[:500]
        elif 'repetitive' in query.lower() or 'manual' in query.lower():
            business_insights['automation_opportunities'] = content[:500]

    # Identify agent opportunities
    agent_opportunities = []
    combined_text = ' '.join(all_content).lower()

    # Check for automation opportunities
    if any(word in combined_text for word in ['manual', 'repetitive', 'time-consuming', 'tedious']):
        agent_opportunities.append(
            {'type': 'automation', 'description': 'Automate repetitive tasks and manual processes', 'impact': 'high'}
        )

    # Check for data management needs
    if any(word in combined_text for word in ['track', 'manage', 'organize', 'store', 'database']):
        agent_opportunities.append(
            {'type': 'data_management', 'description': 'Centralize and organize business data', 'impact': 'high'}
        )

    # Check for customer relationship needs
    if any(word in combined_text for word in ['customer', 'client', 'lead', 'contact', 'follow-up']):
        agent_opportunities.append(
            {'type': 'customer_management', 'description': 'Track and manage customer relationships', 'impact': 'high'}
        )

    # Check for project tracking needs
    if any(word in combined_text for word in ['project', 'task', 'milestone', 'deadline', 'status']):
        agent_opportunities.append(
            {'type': 'project_tracking', 'description': 'Track projects, tasks, and deliverables', 'impact': 'medium'}
        )

    return {
        'insights': business_insights,
        'agent_opportunities': agent_opportunities,
        'data_structure_needs': _infer_data_structures(combined_text, domain),
        'pillar_applications': _identify_pillar_applications(combined_text, domain),
    }


def _infer_data_structures(combined_text: str, domain: str) -> List[Dict[str, Any]]:
    """Infer needed data structures from content."""
    structures = []

    # Common business entities
    if any(word in combined_text for word in ['customer', 'client', 'lead', 'contact']):
        structures.append(
            {
                'name': 'leads',
                'description': 'Customer leads and contacts',
                'fields': ['name', 'email', 'phone', 'source', 'status', 'notes'],
            }
        )

    if any(word in combined_text for word in ['project', 'job', 'assignment', 'work']):
        structures.append(
            {
                'name': 'projects',
                'description': 'Projects and work assignments',
                'fields': ['name', 'status', 'startDate', 'endDate', 'budget', 'notes'],
            }
        )

    if any(word in combined_text for word in ['service', 'offering', 'product', 'package']):
        structures.append(
            {
                'name': 'services',
                'description': 'Services and offerings',
                'fields': ['name', 'description', 'price', 'duration'],
            }
        )

    if any(word in combined_text for word in ['document', 'file', 'pdf', 'image', 'cad']):
        structures.append(
            {
                'name': 'documents',
                'description': 'Business documents and files',
                'fields': ['name', 'type', 'filePath', 'uploadedAt', 'notes'],
            }
        )

    if any(word in combined_text for word in ['questionnaire', 'form', 'survey', 'intake']):
        structures.append(
            {
                'name': 'questionnaires',
                'description': 'Client questionnaires and forms',
                'fields': ['name', 'type', 'url', 'status'],
            }
        )

    return structures


def _identify_pillar_applications(combined_text: str, domain: str) -> Dict[str, List[str]]:
    """Identify how each pillar applies to this business."""
    applications = {'capture': [], 'analyze': [], 'execute': [], 'recall': [], 'grow': []}

    # Capture applications
    if any(word in combined_text for word in ['lead', 'inquiry', 'contact', 'form', 'intake']):
        applications['capture'].append('Capture new customer leads and inquiries')
    if any(word in combined_text for word in ['document', 'file', 'upload', 'scan']):
        applications['capture'].append('Capture and store business documents')
    if any(word in combined_text for word in ['note', 'meeting', 'call', 'conversation']):
        applications['capture'].append('Capture meeting notes and interactions')

    # Analyze applications
    if any(word in combined_text for word in ['trend', 'pattern', 'analysis', 'report', 'statistics']):
        applications['analyze'].append('Analyze business trends and patterns')
    if any(word in combined_text for word in ['score', 'rate', 'evaluate', 'assess', 'priority']):
        applications['analyze'].append('Score and prioritize opportunities')
    if any(word in combined_text for word in ['performance', 'metric', 'kpi', 'dashboard']):
        applications['analyze'].append('Track and analyze performance metrics')

    # Execute applications
    if any(word in combined_text for word in ['generate', 'create', 'export', 'send', 'email']):
        applications['execute'].append('Generate reports and documents')
    if any(word in combined_text for word in ['reminder', 'notification', 'alert', 'follow-up']):
        applications['execute'].append('Send reminders and notifications')
    if any(word in combined_text for word in ['automate', 'workflow', 'process']):
        applications['execute'].append('Automate business workflows')

    # Recall applications
    applications['recall'].append('Search business knowledge base')
    applications['recall'].append('Find similar projects or cases')
    if any(word in combined_text for word in ['history', 'past', 'previous', 'archive']):
        applications['recall'].append('Recall past projects and interactions')

    # Grow applications
    if any(word in combined_text for word in ['learn', 'improve', 'optimize', 'refine']):
        applications['grow'].append('Learn from past projects and outcomes')
    if any(word in combined_text for word in ['template', 'standard', 'best practice']):
        applications['grow'].append('Build templates and best practices')

    return applications


def generate_action_plan(pillars: Dict[str, Any], business_opportunities: Dict[str, Any]) -> Dict[str, Any]:
    """
    Generate concrete action plan from 5 pillars and business opportunities.

    Args:
        pillars: Five pillar mapping
        business_opportunities: Business opportunities analysis

    Returns:
        Action plan with specific capabilities and implementation steps
    """
    plan = {'priority_capabilities': [], 'implementation_steps': [], 'quick_wins': [], 'long_term_goals': []}

    # Sort pillars by relevance
    sorted_pillars = sorted(pillars.items(), key=lambda x: x[1].get('relevance', 0), reverse=True)

    # Generate priority capabilities
    for pillar, data in sorted_pillars[:3]:  # Top 3 pillars
        relevance = data.get('relevance', 0)
        if relevance > 0.6:
            capabilities = data.get('suggested_capabilities', [])
            tools = data.get('suggested_mcp_tools', [])

            plan['priority_capabilities'].append(
                {
                    'pillar': pillar,
                    'relevance': relevance,
                    'capabilities': capabilities[:3],
                    'tools': tools[:3],
                    'applications': business_opportunities.get('pillar_applications', {}).get(pillar, []),
                }
            )

    # Generate implementation steps
    for capability in plan['priority_capabilities']:
        pillar = capability['pillar']
        if pillar == 'capture':
            plan['implementation_steps'].append(
                {
                    'step': f"Implement {pillar} capabilities",
                    'description': f"Set up data capture for: {', '.join(capability['applications'][:2])}",
                    'priority': 'high' if capability['relevance'] > 0.7 else 'medium',
                }
            )
        elif pillar == 'analyze':
            plan['implementation_steps'].append(
                {
                    'step': f"Implement {pillar} capabilities",
                    'description': f"Add analysis features: {', '.join(capability['capabilities'][:2])}",
                    'priority': 'high' if capability['relevance'] > 0.7 else 'medium',
                }
            )
        elif pillar == 'execute':
            plan['implementation_steps'].append(
                {
                    'step': f"Implement {pillar} capabilities",
                    'description': f"Enable automation: {', '.join(capability['applications'][:2])}",
                    'priority': 'medium',
                }
            )

    # Quick wins (high relevance, easy implementation)
    for capability in plan['priority_capabilities']:
        if capability['relevance'] > 0.8 and capability['pillar'] in ['capture', 'recall']:
            plan['quick_wins'].append(
                {
                    'capability': capability['capabilities'][0] if capability['capabilities'] else capability['pillar'],
                    'impact': 'high',
                    'effort': 'low',
                }
            )

    # Long-term goals
    for capability in plan['priority_capabilities']:
        if capability['pillar'] in ['analyze', 'grow']:
            plan['long_term_goals'].append(
                {
                    'goal': f"Advanced {capability['pillar']} capabilities",
                    'description': f"Implement: {', '.join(capability['capabilities'][:2])}",
                    'timeline': '3-6 months',
                }
            )

    return plan


def analyze_content(rag_project_id: str) -> Dict[str, Any]:
    """
    Comprehensive content analysis with business focus.

    Args:
        rag_project_id: RAG project ID

    Returns:
        Complete analysis result matching story-005 spec with business insights
    """
    # Initialize searcher once
    searcher = None
    if RAG_AVAILABLE:
        try:
            user_data_dir = Path.home() / 'Projects' / 'augur' / 'local-rag' / 'projects' / rag_project_id
            searcher = DocumentSearcher(user_data_dir=str(user_data_dir))
        except Exception as e:
            _out(f"Error initializing searcher: {e}", file=sys.stderr)

    # Step 1: Identify domain
    domain_result = identify_domain(rag_project_id, searcher=searcher)
    domain = domain_result['primary']

    # Step 2: Map to pillars
    pillars = map_to_pillars(rag_project_id, domain, searcher=searcher)

    # Step 3: Detect patterns
    patterns = detect_patterns(rag_project_id, searcher=searcher)

    # Step 4: Infer use cases
    use_cases = infer_use_cases(rag_project_id, domain, pillars)

    # Step 5: Extract metadata
    metadata = extract_metadata(rag_project_id, searcher=searcher)

    # Step 6: Analyze business opportunities (NEW)
    business_opportunities = analyze_business_opportunities(rag_project_id, domain, searcher=searcher)

    # Step 7: Generate action plan (NEW)
    action_plan = generate_action_plan(pillars, business_opportunities)

    # Generate suggested skill name
    role = domain_result['role']
    suggested_skill_name = role

    # Determine skill patterns
    structural_types = [p['type'] for p in patterns.get('structural', [])]
    skill_patterns = []
    if 'chronological' in structural_types:
        skill_patterns.append('inbox')
    if any(t in structural_types for t in ['hierarchical', 'structured_forms']):
        skill_patterns.append('database')
    if any(p.get('relevance', 0) > 0.7 for p in pillars.values() if 'analyze' in str(p)):
        skill_patterns.append('scoring')

    if not skill_patterns:
        skill_patterns = ['database']

    return {
        'domain': domain_result,
        'five_pillar_mapping': pillars,
        'patterns': patterns,
        'use_cases': use_cases,
        'metadata': metadata,
        'business_opportunities': business_opportunities,  # NEW
        'action_plan': action_plan,  # NEW
        'suggested_skill': {
            'name': suggested_skill_name,
            'layer': 'vertical',
            'description': domain_result['role_description'],
            'patterns': skill_patterns,
        },
        'summary': f'Content analysis for {domain} domain with {len(use_cases)} use cases identified.',
    }


def main():
    """Main entry point."""
    if len(sys.argv) < 2:
        _out(
            json.dumps(
                {
                    'error': 'RAG project ID required',
                }
            )
        )
        sys.exit(1)

    project_id = sys.argv[1]
    result = analyze_content(project_id)
    _out(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
