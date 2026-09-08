import argparse
import sys


def main(argv=None):
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, 'reconfigure'):
            stream.reconfigure(encoding='utf-8')
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv and argv[0] not in ('serve', '-h', '--help'):
        from mock_dongdong.cli import main as replica_cli
        return replica_cli(argv)
    parser = argparse.ArgumentParser(description='本地客服应用：管理页面、LangGraph 流程与网页自动化')
    parser.add_argument('command', nargs='?', default='serve', choices=['serve'])
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=18766)
    parser.add_argument('--data-dir', default=None)
    args = parser.parse_args(argv)
    from cs_rpa.server import serve
    return serve(args.host, args.port, args.data_dir)


if __name__ == '__main__':
    raise SystemExit(main())
