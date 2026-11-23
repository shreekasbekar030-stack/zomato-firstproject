import { ForkIcon } from "./Icons";

export function SiteHeader() {
  return (
    <header className="bar">
      <a className="brand" href="/">
        <ForkIcon />
        <span>Restaurant finder</span>
      </a>
    </header>
  );
}
