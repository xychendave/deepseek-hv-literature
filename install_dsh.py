"""Register the local stdio MCP service and Skill in existing Harness profiles."""
import argparse
import datetime
import json
import os
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parent
BEGIN = "# BEGIN hv-literature managed block"
END = "# END hv-literature managed block"


def install(dsh_home, profiles, skill_dirs, dry_run=False):
    dsh_home = Path(dsh_home).expanduser().resolve()
    skill = ROOT / "skill/hv-literature"
    row = {"id":"hv-research-mcp", "name":"@deepseek-ai/dsh-mcp-client", "config":{
        "transport":"stdio", "serverName":"hv_research", "command":str(ROOT/"hv-literature"),
        "args":["mcp"], "cwd":str(ROOT), "env":{}, "toolCallTimeoutMs":600000,
        "failOnStartupError":False}}
    # JSON flow-style nodes are valid YAML, without an additional YAML dependency.
    overlay = "- insert:\n    - " + json.dumps(row, ensure_ascii=False) + "\n"
    plans = []
    for profile in dict.fromkeys(profiles):
        if Path(profile).name != profile or profile in (".", ".."):
            raise ValueError("profile 必须是单个目录名")
        directory = dsh_home / "profiles" / profile
        if not directory.is_dir():
            raise ValueError(f"未找到 profile：{directory}；请先启动 Harness 或检查 --dsh-home/--profile")
        path = directory / "cordis.patch.yml"
        before = path.read_text(encoding="utf-8") if path.exists() else ""
        content = before
        if BEGIN in content or END in content:
            if content.count(BEGIN) != 1 or content.count(END) != 1:
                raise ValueError(f"托管块标记不完整：{path}")
            first, last = content.index(BEGIN), content.index(END)
            if last < first:
                raise ValueError(f"托管块顺序错误：{path}")
            content = content[:first] + content[last+len(END):]
        if content.strip() == "[]":
            content = ""
        meaningful = [line for line in content.splitlines() if line.strip() and not line.lstrip().startswith("#")]
        if meaningful and not meaningful[0].lstrip().startswith("-"):
            raise ValueError(f"现有 patch 不是 YAML 列表，请人工检查：{path}")
        after = (content.rstrip()+"\n\n" if content.strip() else "") + BEGIN + "\n" + overlay + END + "\n"
        plans.append((profile, path, before, after))
    links = [Path(p).expanduser().resolve()/"hv-literature" for p in dict.fromkeys(skill_dirs)]
    for link in links:
        if (link.exists() or link.is_symlink()) and link.resolve() != skill.resolve():
            raise ValueError(f"同名 Skill 已存在且指向其他位置，未修改任何配置：{link}")
    stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    installed = []
    for profile, path, before, after in plans:
        record = {"profile":profile, "config":str(path), "changed":before != after}
        if not dry_run and before != after:
            if path.exists():
                backup = path.with_name(path.name+".before-hv-literature-"+stamp)
                shutil.copy2(path, backup)
                record["backup"] = str(backup)
            temporary = path.with_name(path.name+".hv-tmp-"+stamp)
            temporary.write_text(after, encoding="utf-8")
            if path.exists():
                shutil.copymode(path, temporary)
            temporary.replace(path)
        installed.append(record)
    if not dry_run:
        for link in links:
            link.parent.mkdir(parents=True, exist_ok=True)
            if not link.is_symlink():
                link.symlink_to(skill, target_is_directory=True)
        (ROOT/"dsh.patch.yml").write_text(overlay, encoding="utf-8")
    manifest = {"dry_run":dry_run, "installed_at":stamp, "dsh_home":str(dsh_home),
                "profiles":installed, "skill_links":[str(p) for p in links]}
    if not dry_run:
        (ROOT/"data").mkdir(exist_ok=True)
        (ROOT/"data/installation.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dsh-home", default=os.environ.get("DSH_HOME"), help="实际 DSH_HOME 路径；也可用同名环境变量")
    parser.add_argument("--profile", action="append", help="已存在的 profile，可重复指定；默认 desktop")
    parser.add_argument("--skill-dir", action="append", help="Skill 根目录，可重复指定；默认 ~/.agents/skills 与 ~/.codex/skills")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    if not args.dsh_home:
        parser.error("请用 --dsh-home 指定正在使用的 Harness 数据目录，避免误装到其他实例")
    try:
        result = install(args.dsh_home, args.profile or ["desktop"],
                         args.skill_dir or [str(Path.home()/".agents/skills"), str(Path.home()/".codex/skills")], args.dry_run)
    except (ValueError, OSError) as e:
        parser.exit(1, str(e)+"\n")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
