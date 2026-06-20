import { render, screen } from '@testing-library/react';
import { StatCard } from '@/components/ui/StatCard';

describe('StatCard', () => {
  it('renders basic stat card', () => {
    render(<StatCard value="42" label="Recipes" color="cyan" />);
    expect(screen.getByText('42')).toBeInTheDocument();
    expect(screen.getByText('Recipes')).toBeInTheDocument();
  });

  it('renders trend indicator when provided', () => {
    render(<StatCard value="$12,450" label="Portfolio" color="green" trend="+2.3%" />);
    expect(screen.getByText('+2.3%')).toBeInTheDocument();
  });

  it('renders emoji when provided', () => {
    render(<StatCard value="85" label="Health Score" color="cyan" emoji="💪" />);
    expect(screen.getByText('💪')).toBeInTheDocument();
  });

  it('applies custom bgColor class', () => {
    const { container } = render(
      <StatCard value="7" label="Streak" color="green" bgColor="bg-emerald-500/10" />
    );
    expect(container.innerHTML).toContain('bg-emerald');
  });
});
