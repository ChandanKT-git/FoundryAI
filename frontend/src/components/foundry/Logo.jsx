import { Link } from "react-router-dom";

export const Logo = ({ to = "/", small }) => (
  <Link to={to} data-testid="foundry-logo" className="flex items-center gap-2.5 group">
    <span className={`relative grid place-items-center rounded-md bg-[#00F0FF] text-[#0B0F17] font-mono font-bold ${small ? "h-7 w-7 text-xs" : "h-8 w-8 text-sm"} transition-transform duration-300 group-hover:rotate-6`}>
      F<span className="absolute -right-0.5 -top-0.5 h-2 w-2 rounded-full bg-[#10B981] ring-2 ring-[#0B0F17]" />
    </span>
    <span className={`font-display font-extrabold tracking-tight text-white ${small ? "text-base" : "text-lg"}`}>
      Foundry<span className="text-[#00F0FF]">AI</span>
    </span>
  </Link>
);
