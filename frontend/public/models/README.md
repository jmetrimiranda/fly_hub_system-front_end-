# Modelo 3D do drone

Coloque aqui o arquivo `drone.glb` exportado do Hyper3D Rodin.

O binário **não** vai para o Git — o `.gitignore` já cobre `*.glb`. Baixe o
arquivo do storage da equipe ou exporte novamente pelo link do workspace.

Enquanto o arquivo não estiver presente, a aplicação usa o drone de blocos
(`DronePlaceholder`), com exatamente a mesma animação.

As hélices **não** precisam estar separadas: a cena desenha discos de rotor,
que funcionam com um `.glb` de malha única. Separá-las e nomeá-las `prop_fl`,
`prop_fr`, `prop_rl`, `prop_rr` só acrescenta o fade cruzado das pás.

Para conferir o que o exportador produziu:

```bash
node scripts/inspect-glb.mjs frontend/public/models/drone.glb
```

O porquê dos discos está em `docs/drone-3d.md`.
