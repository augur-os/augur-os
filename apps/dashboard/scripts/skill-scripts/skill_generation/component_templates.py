"""Component template generators for the comprehensive dashboard generator.

Generates React component source code for entity panels and RAG search widgets.
"""
from __future__ import annotations

from typing import List, Optional


def entity_to_component_name(entity: str) -> str:
    """Convert entity name to component name."""
    # Convert "symptoms" -> "Symptoms"
    return ''.join(word.capitalize() for word in entity.split('_'))


def generate_entity_component(skill_name: str, entity: str, component_name: str) -> str:
    """Generate interactive component for an entity."""
    entity_singular = entity.rstrip('s') if entity.endswith('s') else entity
    api_path = f'/api/{skill_name}/{entity}'

    return f''''use client';

import {{ useState, useEffect }} from 'react';
import {{ Plus, X, Calendar, Loader2 }} from 'lucide-react';

interface {component_name} {{
  id: string;
  name: string;
  date: string;
  notes?: string;
}}

export default function {component_name}Panel() {{
  const [{entity}, set{component_name}] = useState<{component_name}[]>([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [saving, setSaving] = useState(false);
  const [formData, setFormData] = useState({{
    name: '',
    date: new Date().toISOString().split('T')[0],
    notes: '',
  }});

  useEffect(() => {{
    load{component_name}();
  }}, []);

  const load{component_name} = async () => {{
    try {{
      setLoading(true);
      const response = await fetch('{api_path}');
      const data = await response.json();
      if (data.ok) {{
        set{component_name}(data.{entity});
      }} else {{
        console.error('Failed to load {entity}:', data.error);
      }}
    }} catch (error) {{
      console.error('Failed to load {entity}:', error);
    }} finally {{
      setLoading(false);
    }}
  }};

  const handleSubmit = async (e: React.FormEvent) => {{
    e.preventDefault();
    if (!formData.name.trim()) return;

    try {{
      setSaving(true);
      const response = await fetch('{api_path}', {{
        method: 'POST',
        headers: {{ 'Content-Type': 'application/json' }},
        body: JSON.stringify({{
          name: formData.name,
          date: formData.date,
          notes: formData.notes || undefined,
        }}),
      }});

      const data = await response.json();
      if (data.ok) {{
        const new{component_name} = data.{entity_singular};
        set{component_name}([new{component_name}, ...{entity}]);
        setFormData({{
          name: '',
          date: new Date().toISOString().split('T')[0],
          notes: '',
        }});
        setShowForm(false);
      }} else {{
        console.error('Failed to save {entity_singular}:', data.error);
      }}
    }} catch (error) {{
      console.error('Failed to save {entity_singular}:', error);
    }} finally {{
      setSaving(false);
    }}
  }};

  const handleDelete = async (id: string) => {{
    if (!confirm('Are you sure you want to delete this {entity_singular}?')) return;

    try {{
      const response = await fetch(`{api_path}?id=${{id}}`, {{
        method: 'DELETE',
      }});

      const data = await response.json();
      if (data.ok) {{
        set{component_name}({entity}.filter((item) => item.id !== id));
      }} else {{
        console.error('Failed to delete {entity_singular}:', data.error);
      }}
    }} catch (error) {{
      console.error('Failed to delete {entity_singular}:', error);
    }}
  }};

  if (loading) {{
    return (
      <div className="flex items-center justify-center p-8">
        <Loader2 className="w-6 h-6 animate-spin text-cyan-400" />
      </div>
    );
  }}

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold text-neutral-300">{component_name}</h3>
        <button
          onClick={{() => setShowForm(!showForm)}}
          className="flex items-center gap-1 px-2 py-1 text-xs bg-cyan-500/20 text-cyan-400 rounded hover:bg-cyan-500/30"
        >
          <Plus className="w-3 h-3" />
          Add
        </button>
      </div>

      {{showForm && (
        <form onSubmit={{handleSubmit}} className="p-3 rounded-lg bg-neutral-900/50 border border-neutral-800 space-y-2">
          <input
            type="text"
            value={{formData.name}}
            onChange={{e => setFormData({{ ...formData, name: e.target.value }})}}
            placeholder="Name"
            className="w-full px-3 py-2 bg-neutral-800 border border-neutral-700 rounded text-sm text-white placeholder:text-neutral-500 focus:outline-none focus:border-cyan-500"
            required
          />
          <input
            type="date"
            value={{formData.date}}
            onChange={{e => setFormData({{ ...formData, date: e.target.value }})}}
            className="w-full px-3 py-2 bg-neutral-800 border border-neutral-700 rounded text-sm text-white focus:outline-none focus:border-cyan-500"
          />
          <textarea
            value={{formData.notes}}
            onChange={{e => setFormData({{ ...formData, notes: e.target.value }})}}
            placeholder="Notes (optional)"
            rows={2}
            className="w-full px-3 py-2 bg-neutral-800 border border-neutral-700 rounded text-sm text-white placeholder:text-neutral-500 focus:outline-none focus:border-cyan-500 resize-none"
          />
          <div className="flex gap-2">
            <button
              type="submit"
              disabled={{saving}}
              className="flex-1 px-3 py-1.5 text-xs bg-cyan-500/20 text-cyan-400 rounded hover:bg-cyan-500/30 disabled:opacity-50"
            >
              {{saving ? 'Saving...' : 'Save'}}
            </button>
            <button
              type="button"
              onClick={{() => setShowForm(false)}}
              className="px-3 py-1.5 text-xs bg-neutral-800 text-neutral-400 rounded hover:bg-neutral-700"
            >
              Cancel
            </button>
          </div>
        </form>
      )}}

      <div className="space-y-2 max-h-64 overflow-y-auto">
        {{{entity}.length === 0 ? (
          <p className="text-xs text-neutral-500 text-center py-4">No {entity} yet</p>
        ) : (
          {entity}.map((item) => (
            <div
              key={{item.id}}
              className="p-2 rounded bg-neutral-900/50 border border-neutral-800 flex items-start justify-between"
            >
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2">
                  <span className="text-sm text-white font-medium">{{item.name}}</span>
                  <span className="text-xs text-neutral-500">
                    <Calendar className="w-3 h-3 inline mr-1" />
                    {{new Date(item.date).toLocaleDateString()}}
                  </span>
                </div>
                {{item.notes && (
                  <p className="text-xs text-neutral-400 mt-1">{{item.notes}}</p>
                )}}
              </div>
              <button
                onClick={{() => handleDelete(item.id)}}
                className="p-1 text-neutral-500 hover:text-red-400 transition-colors"
              >
                <X className="w-4 h-4" />
              </button>
            </div>
          ))
        )}}
      </div>
    </div>
  );
}}
'''


def generate_rag_search_component(skill_name: str, skill_title: str) -> str:
    """Generate RAG search component."""
    component_name = skill_title.replace(' ', '')
    return f''''use client';

import {{ useState }} from 'react';
import {{ Search, Loader2 }} from 'lucide-react';

export default function {component_name}SearchPanel() {{
  const [query, setQuery] = useState('');
  const [results, setResults] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);

  const handleSearch = async (e: React.FormEvent) => {{
    e.preventDefault();
    if (!query.trim()) return;

    try {{
      setLoading(true);
      const response = await fetch('/api/{skill_name}/search', {{
        method: 'POST',
        headers: {{ 'Content-Type': 'application/json' }},
        body: JSON.stringify({{ query }}),
      }});

      if (response.ok) {{
        const data = await response.json();
        setResults(data);
      }}
    }} catch (error) {{
      console.error('Search failed:', error);
    }} finally {{
      setLoading(false);
    }}
  }};

  return (
    <div className="space-y-4">
      <form onSubmit={{handleSearch}} className="flex gap-2">
        <input
          type="text"
          value={{query}}
          onChange={{e => setQuery(e.target.value)}}
          placeholder="Search knowledge base..."
          className="flex-1 px-3 py-2 bg-neutral-800 border border-neutral-700 rounded text-sm text-white placeholder:text-neutral-500 focus:outline-none focus:border-cyan-500"
        />
        <button
          type="submit"
          disabled={{loading || !query.trim()}}
          className="px-4 py-2 bg-cyan-500/20 text-cyan-400 rounded hover:bg-cyan-500/30 disabled:opacity-50 flex items-center gap-2"
        >
          {{loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Search className="w-4 h-4" />}}
          Search
        </button>
      </form>

      {{results.length > 0 && (
        <div className="space-y-2 max-h-96 overflow-y-auto">
          {{results.map((result, idx) => (
            <div
              key={{idx}}
              className="p-3 rounded bg-neutral-900/50 border border-neutral-800"
            >
              <p className="text-sm text-neutral-300">{{result.preview || result.content}}</p>
              {{result.source && (
                <p className="text-xs text-neutral-500 mt-1">{{result.source}}</p>
              )}}
            </div>
          ))}}
        </div>
      )}}
    </div>
  );
}}
'''
