/**
 * @jest-environment jsdom
 */
import { fireEvent, render, screen } from '@testing-library/react';
import '@testing-library/jest-dom';
import type { ReactNode } from 'react';
import { HumanApiProfile } from '@/features/pages/workspace/memory/components/HumanApiProfile';

jest.mock('@/features/components/DashboardWidget', () => ({
  __esModule: true,
  default: ({ children, title }: { children: ReactNode; title: string }) => (
    <section aria-label={title}>{children}</section>
  ),
}));

describe('HumanApiProfile', () => {
  it('shows notice and error blocks above the profile body', () => {
    render(
      <HumanApiProfile
        profile={{
          exists: true,
          role: 'Engineer',
          expertise: ['systems'],
          communicationStyle: 'concise',
          successCriteria: ['Clear next steps'],
          contextGaps: ['Unknown availability'],
          lastUpdated: '2026-04-22T10:00:00.000Z',
          rawContent: '',
        }}
        editedProfile={null}
        setEditedProfile={jest.fn()}
        isEditing={false}
        setIsEditing={jest.fn()}
        isSaving={false}
        isRegenerating={false}
        onSave={jest.fn()}
        onRegenerate={jest.fn()}
        onCancel={jest.fn()}
        notice={{ type: 'success', message: 'Profile saved.', timestamp: '2026-04-22T10:01:00.000Z' }}
        error="Save profile failed: conflict"
      />,
    );

    expect(screen.getByText('Profile saved.')).toBeInTheDocument();
    expect(screen.getByText('Save profile failed: conflict')).toBeInTheDocument();
    expect(screen.getByText('Engineer')).toBeInTheDocument();
  });

  it('keeps profile metadata and actions in a responsive wrapping header', () => {
    render(
      <HumanApiProfile
        profile={{
          exists: true,
          role: 'Engineer',
          expertise: ['systems'],
          communicationStyle: 'concise',
          successCriteria: ['Clear next steps'],
          contextGaps: ['Unknown availability'],
          lastUpdated: '2026-04-22T10:00:00.000Z',
          rawContent: '',
        }}
        editedProfile={null}
        setEditedProfile={jest.fn()}
        isEditing={false}
        setIsEditing={jest.fn()}
        isSaving={false}
        isRegenerating={false}
        onSave={jest.fn()}
        onRegenerate={jest.fn()}
        onCancel={jest.fn()}
      />,
    );

    expect(screen.getByText(/Auto-generated from session patterns/).parentElement).toHaveClass('flex-col');
    expect(screen.getByRole('button', { name: /edit/i }).parentElement).toHaveClass('w-full');
  });

  it('disables regenerate while profile generation is running', () => {
    render(
      <HumanApiProfile
        profile={{
          exists: true,
          role: 'Engineer',
          expertise: ['systems'],
          communicationStyle: 'concise',
          successCriteria: ['Clear next steps'],
          contextGaps: ['Unknown availability'],
          lastUpdated: '2026-04-22T10:00:00.000Z',
          rawContent: '',
        }}
        editedProfile={null}
        setEditedProfile={jest.fn()}
        isEditing={false}
        setIsEditing={jest.fn()}
        isSaving={false}
        isRegenerating={true}
        onSave={jest.fn()}
        onRegenerate={jest.fn()}
        onCancel={jest.fn()}
      />,
    );

    expect(screen.getByRole('button', { name: /regenerating/i })).toBeDisabled();
  });

  it('shows profile provenance, confidence, and missing-field edit prompts', () => {
    const setIsEditing = jest.fn();

    render(
      <HumanApiProfile
        profile={{
          exists: true,
          role: '',
          expertise: ['systems'],
          communicationStyle: 'concise',
          successCriteria: [],
          contextGaps: ['Unknown availability'],
          lastUpdated: '2026-04-22T10:00:00.000Z',
          rawContent: '# Human API Profile\n\n## Communication Style\nconcise',
        }}
        editedProfile={null}
        setEditedProfile={jest.fn()}
        isEditing={false}
        setIsEditing={setIsEditing}
        isSaving={false}
        isRegenerating={false}
        onSave={jest.fn()}
        onRegenerate={jest.fn()}
        onCancel={jest.fn()}
      />,
    );

    expect(screen.getByText('Profile provenance')).toBeInTheDocument();
    expect(screen.getByText(/knowledge-memory-profile/i)).toBeInTheDocument();
    expect(screen.getByText(/Profile confidence/i)).toHaveTextContent('Low');
    expect(screen.getByText('Missing fields')).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: /add role/i }));

    expect(setIsEditing).toHaveBeenCalledWith(true);
  });
});
