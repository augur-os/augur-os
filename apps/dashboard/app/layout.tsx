import type { Metadata } from "next";
import { Inter, Lora, Fira_Code, Fira_Sans } from "next/font/google";
import "./globals.css";

import SidebarNav from "../components/SidebarNav";
import KeyboardShortcutsProvider from "../components/KeyboardShortcutsProvider";
import BrainLogo from "../components/BrainLogo";
import GlobalShell from "../components/GlobalShell";
import MobileSidebar from "../components/MobileSidebar";

// Load Inter font with optimized subsets
const inter = Inter({
  subsets: ["latin"],
  display: "swap",
  variable: "--font-inter",
  weight: ["400", "500", "600", "700"],
});

const lora = Lora({
  subsets: ["latin"],
  display: "swap",
  variable: "--font-lora",
  weight: ["400", "500", "600", "700"],
});

const firaCode = Fira_Code({
  subsets: ["latin"],
  display: "swap",
  variable: "--font-fira-code",
  weight: ["400", "600"],
});

const firaSans = Fira_Sans({
  subsets: ["latin"],
  display: "swap",
  variable: "--font-fira-sans",
  weight: ["300", "400", "500", "600", "700"],
});

export const metadata: Metadata = {
  metadataBase: new URL(
    process.env.NEXT_PUBLIC_BASE_URL || "http://localhost:3000",
  ),
  title: "Augur | Dashboard",
  description: "AI Augmentation Atrium - The heart of your augur",
};

import PerformanceTracker from "../components/PerformanceTracker";
import ContextManager from "../components/ContextManager";
import UsageTracker from "../components/UsageTracker";
import ClientErrorReporter from "../components/ClientErrorReporter";
import { Suspense } from "react";
import { ThemeInitializer } from "../hooks/useTheme";
import { PluginEventNotifier } from "../components/plugin-wizard/PluginEventNotifier";
import { QueryProvider } from "../components/QueryProvider";
import { WebMCPProvider } from "@/lib/webmcp/WebMCPProvider";
import McpStatusBanner from "../components/McpStatusBanner";
import ContinueInSessionListener from "../components/session/ContinueInSessionListener";
import SessionPrewarmer from "../components/session/SessionPrewarmer";

const THEME_INIT_SCRIPT = `(function(){try{
  var t=localStorage.getItem('augur:theme:v2')||'futuristic';
  var m=localStorage.getItem('augur:theme-mode:v1')||'system';
  var isDark=m==='dark'||(m==='system'&&window.matchMedia('(prefers-color-scheme:dark)').matches);
  var mode=isDark?'dark':'light';
  var theme=isDark?t:t+'-light';
  document.documentElement.setAttribute('data-theme',theme);
  document.documentElement.setAttribute('data-mode',mode);
  document.documentElement.style.colorScheme=mode;
}catch(e){}})();`;

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html
      lang="en"
      className={`${inter.variable} ${lora.variable} ${firaCode.variable} ${firaSans.variable}`}
      data-theme="futuristic-light"
      data-mode="light"
      style={{ colorScheme: "light" }}
      suppressHydrationWarning
    >
      <head>
        <script
          id="theme-init"
          dangerouslySetInnerHTML={{ __html: THEME_INIT_SCRIPT }}
        />
      </head>
      <body
        className="flex flex-col md:flex-row h-screen bg-[var(--bg-primary)] text-[var(--text-primary)] overflow-hidden"
        suppressHydrationWarning
      >
        <ThemeInitializer />
        <PerformanceTracker />
        <ClientErrorReporter />
        <ContextManager />
        <UsageTracker />
        <KeyboardShortcutsProvider>
          {/* Skip Navigation Link - Accessibility */}
          <a
            href="#main-content"
            className="sr-only focus:not-sr-only focus:absolute focus:top-4 focus:left-4 focus:z-50 focus:px-4 focus:py-2 focus:bg-[var(--accent-primary)] focus:text-[var(--text-on-accent,#fff)] focus:rounded-lg focus:shadow-lg focus:outline-none focus:ring-2 focus:ring-[var(--accent-primary)] focus:ring-offset-2 focus:ring-offset-[var(--bg-primary)]"
          >
            Skip to main content
          </a>
          {/* Mobile Sidebar with hamburger menu */}
          <QueryProvider>
            <WebMCPProvider>
              <SessionPrewarmer />
              <ContinueInSessionListener />
              <PluginEventNotifier />
              <MobileSidebar />

              {/* Desktop Sidebar */}
              <aside className="hidden md:flex w-64 border-r border-[var(--border-color)] p-6 flex-col gap-4 bg-[var(--bg-sidebar)] backdrop-blur-md">
                <BrainLogo />

                <SidebarNav />

              </aside>

              {/* Main Content */}
              <main
                id="main-content"
                className="flex-1 overflow-y-auto p-4 pb-[calc(6rem+env(safe-area-inset-bottom))] md:p-8 md:pb-8 relative"
                tabIndex={-1}
              >
                {/* Animated gradient overlays - hidden in light mode */}
                <div className="gradient-overlay absolute top-0 left-0 w-full h-full pointer-events-none overflow-hidden transition-opacity duration-300 motion-reduce:hidden">
                  <div
                    className="absolute top-0 left-0 w-full max-w-2xl h-[40rem] bg-gradient-to-br from-cyan-500/10 via-purple-500/10 to-transparent rounded-full blur-3xl animate-pulse"
                  />
                  <div
                    className="absolute top-1/4 right-0 w-full max-w-xl h-[32rem] bg-gradient-to-bl from-purple-500/10 via-pink-500/10 to-transparent rounded-full blur-3xl animate-pulse"
                  />
                  <div
                    className="absolute bottom-0 left-1/3 w-full max-w-sm h-96 bg-gradient-to-tr from-emerald-500/10 via-cyan-500/10 to-transparent rounded-full blur-3xl animate-pulse"
                  />
                </div>
                {/* Content gradient overlay - hidden in light mode */}
                <div className="content-gradient absolute top-0 left-0 w-full h-96 bg-gradient-to-b from-purple-900/20 via-transparent to-transparent pointer-events-none z-0 transition-opacity duration-300" />
                <Suspense>
                  <div className="relative z-10 max-w-7xl mx-auto">
                    {children}
                  </div>
                </Suspense>
                <GlobalShell />
                <McpStatusBanner />
              </main>
            </WebMCPProvider>
          </QueryProvider>
        </KeyboardShortcutsProvider>
      </body>
    </html>
  );
}
