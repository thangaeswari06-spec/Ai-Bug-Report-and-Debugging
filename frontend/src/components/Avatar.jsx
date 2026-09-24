export default function Avatar({ user, size = 36 }) {
  const initials = (user?.name || user?.email || "?").split(/\s+/).map((w) => w[0]).slice(0, 2).join("").toUpperCase();
  const style = { width: size, height: size, fontSize: size * 0.38 };
  if (user?.avatar) return <img src={user.avatar} alt={user.name} className="avatar" style={style} />;
  return <span className="avatar" style={style}>{initials}</span>;
}
