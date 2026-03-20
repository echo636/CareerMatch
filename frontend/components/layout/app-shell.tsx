import Link from "next/link";
import type { PropsWithChildren } from "react";

const navItems = [
  { href: "/", label: "架构总览" },
  { href: "/resume", label: "简历处理" },
  { href: "/matches", label: "匹配结果" },
  { href: "/admin/jobs", label: "岗位导入" },
] as const;

type AppRoute = (typeof navItems)[number]["href"];

type AppShellProps = PropsWithChildren<{
  activePath: AppRoute;
}>;

export function AppShell({ activePath, children }: AppShellProps) {
  return (
    <div className="page-shell">
      <header className="topbar">
        <div>
          <p className="eyebrow">CareerMatch</p>
          <h1>AI 简历岗位智能匹配系统</h1>
        </div>
        <nav className="nav-grid" aria-label="Primary navigation">
          {navItems.map((item) => {
            const isActive = activePath === item.href;
            return (
              <Link
                key={item.href}
                href={item.href}
                className={isActive ? "nav-link nav-link-active" : "nav-link"}
              >
                {item.label}
              </Link>
            );
          })}
        </nav>
      </header>
      <main className="content-grid">{children}</main>
    </div>
  );
}