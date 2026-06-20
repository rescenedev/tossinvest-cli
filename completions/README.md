# 셸 자동완성 (Shell Completion)

`toss` 명령의 서브커맨드·옵션을 `<TAB>` 으로 자동완성합니다.
스크립트는 `toss` 바이너리에 동적으로 질의하므로, 커맨드가 추가/변경돼도
별도 수정 없이 항상 최신 목록을 따라갑니다.

## 가장 간단한 방법 (권장)

Typer 내장 설치 명령을 쓰면 현재 셸을 자동 감지해 설정까지 마칩니다.

```bash
toss --install-completion
# 적용하려면 셸을 새로 열거나: exec $SHELL
```

스크립트 내용만 확인하려면:

```bash
toss --show-completion
```

## 수동 설치

이 디렉터리의 스크립트를 직접 사용할 수도 있습니다.

### bash

```bash
# 일회성 적용 (현재 셸에만)
source completions/toss.bash

# 영구 적용
mkdir -p ~/.bash_completion.d
cp completions/toss.bash ~/.bash_completion.d/toss
echo 'source ~/.bash_completion.d/toss' >> ~/.bashrc
```

> macOS 기본 bash(3.2)에서도 동작합니다. `bash-completion` 패키지가 있으면
> 시스템 디렉터리(`$(brew --prefix)/etc/bash_completion.d/`)에 복사해도 됩니다.

### zsh

```zsh
# fpath 에 있는 디렉터리에 _toss 를 둡니다.
mkdir -p ~/.zfunc
cp completions/_toss ~/.zfunc/_toss

# ~/.zshrc 에 (compinit 보다 위에) 추가:
fpath=(~/.zfunc $fpath)
autoload -Uz compinit && compinit
```

### fish

```fish
cp completions/toss.fish ~/.config/fish/completions/toss.fish
```

## 동작 원리

각 스크립트는 셸이 자동완성을 요청할 때 `_TOSS_COMPLETE` 환경변수를 설정해
`toss` 를 다시 호출하고, 그 출력(후보 목록)을 셸에 돌려줍니다.
정적 목록을 하드코딩하지 않으므로 유지보수가 필요 없습니다.
