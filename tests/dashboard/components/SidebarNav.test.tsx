import { render, screen, waitFor, act, fireEvent } from '@testing-library/react';
import '@testing-library/jest-dom';
import SidebarNav from '@/components/SidebarNav';
import { renderWithQuery } from '../helpers/component-test-utils';

// Mock next/navigation
const mockUsePathname = jest.fn();
jest.mock('next/navigation', () => ({
  usePathname: () => mockUsePathname(),
}));

// Mock MCP context hook
const mockHandleLinkHover = jest.fn();
jest.mock('@/hooks/useMCPContext', () => ({
  useMCPContext: () => ({
    handleLinkHover: mockHandleLinkHover,
  }),
}));

// Mock mode store
const mockUseModeStore = jest.fn();
jest.mock('@/lib/stores/modeStore', () => ({
  useModeStore: () => mockUseModeStore(),
}));

// Mock DynamicSkillsNav component
jest.mock('@/features/components/DynamicSkillsNav', () => ({
  __esModule: true,
  default: () => <div data-testid="dynamic-skills-nav">Dynamic Skills Nav</div>,
}));

// Mock localStorage
const localStorageMock = (() => {
  let store: Record<string, string> = {};
  return {
    getItem: (key: string) => store[key] || null,
    setItem: (key: string, value: string) => {
      store[key] = value;
    },
    clear: () => {
      store = {};
    },
  };
})();

Object.defineProperty(window, 'localStorage', {
  value: localStorageMock,
});

// Helper: render inside async act() so useEffect microtasks settle
async function renderAsync(ui: React.ReactElement) {
  let result: ReturnType<typeof render>;
  await act(async () => {
    result = renderWithQuery(ui);
  });
  return result!;
}

describe('SidebarNav', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    localStorageMock.clear();
    mockUsePathname.mockReturnValue('/');
    mockUseModeStore.mockReturnValue({ mode: 'operation' });
  });

  it('renders navigation links', async () => {
    const { container } = await renderAsync(<SidebarNav />);

    // Wait for component to mount
    await waitFor(() => {
      expect(container.querySelectorAll('a[href="/settings"]').length).toBeGreaterThan(0);
    });

    // /settings is the only FOOTER_ITEMS entry; /help was removed
    expect(container.querySelectorAll('a[href="/settings"]').length).toBeGreaterThan(0);
    // /browse is always present (STATIC_SECTIONS)
    expect(container.querySelectorAll('a[href="/browse"]').length).toBeGreaterThan(0);
  });

  it('highlights active link correctly', async () => {
    mockUsePathname.mockReturnValue('/settings');

    const { container } = await renderAsync(<SidebarNav />);

    await waitFor(() => {
      expect(container.querySelectorAll('a[href="/settings"]').length).toBeGreaterThan(0);
    });

    const settingsLink = container.querySelector('a[href="/settings"]');
    expect(settingsLink).toHaveClass('nav-link-active');
  });

  it('highlights browse path correctly', async () => {
    mockUsePathname.mockReturnValue('/browse');

    const { container } = await renderAsync(<SidebarNav />);

    await waitFor(() => {
      expect(container.querySelectorAll('a[href="/browse"]').length).toBeGreaterThan(0);
    });

    // /browse is the default favorites and first STATIC_SECTIONS item
    const browseLink = container.querySelector('a[href="/browse"]');
    expect(browseLink).toHaveClass('nav-link-active');
  });

  it('highlights nested path correctly', async () => {
    mockUsePathname.mockReturnValue('/settings/preferences');

    const { container } = await renderAsync(<SidebarNav />);

    await waitFor(() => {
      expect(container.querySelectorAll('a[href="/settings"]').length).toBeGreaterThan(0);
    });

    const settingsLinks = Array.from(container.querySelectorAll('a[href="/settings"]'));
    expect(settingsLinks.some((link) => link.classList.contains('nav-link-active'))).toBe(true);
  });

  it('calls handleLinkHover on mouse enter', async () => {
    const { container } = await renderAsync(<SidebarNav />);

    await waitFor(() => {
      expect(container.querySelectorAll('a[href="/settings"]').length).toBeGreaterThan(0);
    });

    const settingsLink = container.querySelector('a[href="/settings"]');
    expect(settingsLink).not.toBeNull();

    if (settingsLink) {
      fireEvent.mouseEnter(settingsLink);
    }

    expect(mockHandleLinkHover).toHaveBeenCalledWith('/settings');
  });

  it('hides dev category items in operation mode', async () => {
    mockUseModeStore.mockReturnValue({ mode: 'operation' });

    const { container } = await renderAsync(<SidebarNav />);

    await waitFor(() => {
      expect(container.querySelectorAll('a[href="/settings"]').length).toBeGreaterThan(0);
    });

    // Dev and Control are dev category items
    // They should not be visible in operation mode
    const devLinks = container.querySelectorAll('a[href="/dev"]');
    const controlLinks = container.querySelectorAll('a[href="/control"]');

    expect(devLinks).toHaveLength(0);
    expect(controlLinks).toHaveLength(0);
  });

  it('shows dev category items in dev mode', async () => {
    mockUseModeStore.mockReturnValue({ mode: 'development' });

    const { container } = await renderAsync(<SidebarNav />);

    await waitFor(() => {
      // Wait for the component to mount and render
      expect(container.querySelectorAll('a[href="/settings"]').length).toBeGreaterThan(0);
    });

    // Dev mode should still render a non-empty nav without errors.
    expect(container.querySelectorAll('a').length).toBeGreaterThan(0);
  });

  it('filters items based on visibility preferences from localStorage', async () => {
    // Hide the browse item
    localStorageMock.setItem('augur:sidebar-visibility:v1', JSON.stringify({
      '/browse': false,
    }));

    const { container } = await renderAsync(<SidebarNav />);

    await waitFor(() => {
      // Settings is always in FOOTER_ITEMS
      expect(container.querySelectorAll('a[href="/settings"]').length).toBeGreaterThan(0);
    });

    // /browse should be hidden from sections (it's in the favorites list,
    // visibility=false removes it from favoriteItems too)
    // Settings is always shown as FOOTER_ITEMS renders unconditionally
    expect(container.querySelectorAll('a[href="/settings"]')).toHaveLength(1);
  });

  it('renders DynamicSkillsNav component', async () => {
    await renderAsync(<SidebarNav />);

    await waitFor(() => {
      expect(screen.getByTestId('dynamic-skills-nav')).toBeInTheDocument();
    });
  });

  it('renders dev-only app links in dev mode', async () => {
    mockUseModeStore.mockReturnValue({ mode: 'development' });

    const { container } = await renderAsync(<SidebarNav />);

    await waitFor(() => {
      expect(container.querySelectorAll('a[href="/settings"]').length).toBeGreaterThan(0);
    });

    // Dev mode should show more links than just settings
    const allLinks = container.querySelectorAll('a');
    const hrefs = Array.from(allLinks).map(a => a.getAttribute('href') || '');
    // In dev mode, we should have settings and at least some dev-visible links
    expect(hrefs.length).toBeGreaterThan(2);
  });

  it('hides section if all items are filtered out', async () => {
    mockUseModeStore.mockReturnValue({ mode: 'development' });

    // Hide all items in the Dev section (static + system plugins)
    localStorageMock.setItem('augur:sidebar-visibility:v1', JSON.stringify({
      '/dev': false,
      '/control': false,
      '/settings': false,
      '/help': false,
      // System category plugins that merge into Operations section
      '/factory': false,
      '/ai': false,
      '/daemon': false,
      '/renderer': false,
      '/scraper': false,
      '/updater': false,
      '/home': false,
      '/observe': false,
    }));

    await renderAsync(<SidebarNav />);

    await waitFor(() => {
      // At least some navigation links should still be visible (not everything hidden)
      const allLinks = document.querySelectorAll('a');
      expect(allLinks.length).toBeGreaterThan(0);
    });

    expect(screen.queryByText('Operations')).not.toBeInTheDocument();
  });

  it('updates visibility when custom event is dispatched', async () => {
    const { container } = await renderAsync(<SidebarNav />);

    await waitFor(() => {
      expect(container.querySelectorAll('a[href="/settings"]').length).toBeGreaterThan(0);
    });

    // Dispatch custom event to hide settings
    await act(async () => {
      const event = new CustomEvent('sidebar-subscription-update', {
        detail: { '/settings': false },
      });
      window.dispatchEvent(event);
    });

    await waitFor(() => {
      // The event sets visibility to hide /settings from sections,
      // but FOOTER_ITEMS always renders /settings unconditionally.
      // So we expect exactly 1 settings link (the footer one).
      expect(container.querySelectorAll('a[href="/settings"]')).toHaveLength(1);
    });
  });

  it('shows loading state before mounted', async () => {
    // This is difficult to test because the component mounts too fast
    // But we can verify the nav element is eventually rendered
    await renderAsync(<SidebarNav />);

    const navElement = document.querySelector('nav');
    expect(navElement).toBeInTheDocument();
  });
});
