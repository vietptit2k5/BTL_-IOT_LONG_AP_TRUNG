#!/usr/bin/env bash
# Run on the Raspberry Pi, in the same folder as both Python files.
set -eu

cd "$(dirname "$0")"
gpio_ready=0

cleanup() {
    local result=$?
    trap - EXIT
    trap '' INT TERM HUP
    if [ "$gpio_ready" -eq 1 ]; then
        if ! python3 ./thu_mach_12v.py tat; then
            printf '\nKhong gui duoc lenh TAT. Rut adapter 12 V cap cho bong/quat.\n' >&2
            if [ "$result" -eq 0 ]; then result=1; fi
        fi
    fi
    exit "$result"
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
trap 'exit 129' HUP

confirm_or_stop() {
    local answer
    while true; do
        printf '%s [y=chay, n=dung]: ' "$1"
        if ! read -r answer; then
            printf '\nKhong doc duoc tra loi. Dung thu va gui lenh tat.\n' >&2
            exit 1
        fi
        answer=${answer%$'\r'}
        case "$answer" in
            y|Y) return 0 ;;
            n|N) printf 'Dung thu theo lua chon.\n'; exit 0 ;;
            *) printf 'Chi nhap mot chu y hoac n, roi nhan Enter. Day khong phai o nhap thoi gian/cong suat.\n' ;;
        esac
    done
}

printf '\nTHU HAI MOSFET: BONG 12 V / QUAT 12 V\n'
printf 'GPIO23 (chan 16): bong. GPIO18 (chan 12): quat.\n'
printf 'Ban dau giu adapter 12 V dang rut; Pi lay USB-C rieng.\n\n'

if ! command -v python3 >/dev/null 2>&1; then
    printf 'Pi chua co python3. Dung lai de kiem tra he dieu hanh.\n' >&2
    exit 1
fi
for code_file in thu_mach.py thu_mach_12v.py; do
    if [ ! -f "$code_file" ]; then
        printf 'Thieu %s. Can chep ca thu muc Code_HopAp_Demo.\n' "$code_file" >&2
        exit 1
    fi
done

printf 'Kiem tra thu vien GPIO...\n'
if ! python3 -c 'import gpiozero; import lgpio; from gpiozero.pins.lgpio import LGPIOFactory' >/dev/null 2>&1; then
    printf 'Can Internet tren Pi de cai cac goi con thieu.\n'
    sudo apt update
    sudo apt install -y python3-gpiozero python3-lgpio
fi
python3 -c 'import gpiozero; import lgpio; from gpiozero.pins.lgpio import LGPIOFactory'

gpio_ready=1
python3 ./thu_mach_12v.py tat

printf '\nMo nap, de hop rong va kiem tra bong da gan chac, tach khoi xop.\n'
printf 'Cam adapter 12 V; ca bong va quat phai con TAT.\n'
printf 'Neu tai tu bat: rut adapter 12 V va nhan Ctrl+C.\n'
confirm_or_stop 'San sang thu quat 5 giay?'

printf '\nThu quat 100%% trong 5 giay...\n'
python3 ./thu_mach_12v.py quat --giay 5

printf '\n'
confirm_or_stop 'Quat da quay roi tat dung lenh? Thu bong 2 giay?'

printf '\nThu bong 2 giay, sau do quat chay them 5 giay...\n'
python3 ./thu_mach_12v.py den --giay 2
printf '\nDa chay xong cac lenh thu. Kiem tra thuc te ca hai tai da tat.\n'
printf 'Rut adapter 12 V sau buoi thu. Day khong phai che do dieu nhiet.\n'
