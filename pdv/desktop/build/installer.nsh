; Regra do Firewall do Windows para a cozinha abrir o painel pela rede local (RF-23, DEC-11).
; Só redes privadas. Pede permissão de administrador uma vez, na primeira instalação;
; atualizações automáticas não mexem na regra (o caminho do programa é o mesmo).

!macro customInstall
  ${ifNot} ${isUpdated}
    ExecShell "runas" "$SYSDIR\cmd.exe" '/c netsh advfirewall firewall delete rule name="PDV Restaurantes" >nul 2>&1 & netsh advfirewall firewall add rule name="PDV Restaurantes" dir=in action=allow program="$INSTDIR\PDV Restaurantes.exe" enable=yes profile=private' SW_HIDE
  ${endIf}
!macroend

!macro customUnInstall
  ${ifNot} ${isUpdated}
    ExecShell "runas" "$SYSDIR\cmd.exe" '/c netsh advfirewall firewall delete rule name="PDV Restaurantes"' SW_HIDE
  ${endIf}
!macroend
