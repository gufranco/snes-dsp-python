# Cartridges go here

Nothing in this directory is committed, and nothing in it ships.

The firmware beside this tells the part what to compute. A cartridge tells it
*how to be asked*: how many bytes go each way for each command, in what order,
and how wide each transfer is. That is not written down anywhere else, because
the game and the chip were built together and only had to agree with each other.

So the game is the authority on its own protocol, and the way to read that
authority is to run the routine inside it that drives the chip. A copy you
already own goes here, under whatever name it already has.

## What belongs here

Every file is identified by its digest before it is read, never by its name, and
all four digests are checked rather than only the one that decides. Any file
ending `.sfc` or `.smc` is looked at.

**Only retail releases.** A modified release can carry altered code, and a driver
routine read out of one would describe somebody's edit rather than the part. Every
region of every title is wanted, because the driver routine can differ between
them.

36 cartridges, 23 distinct titles:

| File | Bytes | CRC32 | SHA-256 |
|:-----|------:|:------|:--------|
| `3-jigen Kakutou Ballz (Japan).sfc` | 1,048,576 | `f0810694` | `1b59feccf5df19265b1885ea8e0ae85693a19650de338e898f4999f639695402` |
| `Ace o Nerae! (Japan).sfc` | 1,048,576 | `6c5f1a18` | `9c9373e2a078ae47469d835fb4750ad0e4a46156c73baf573d3fabd132f5c184` |
| `Ballz 3D - Fighting at Its Ballziest (USA).sfc` | 1,048,576 | `1c058b7d` | `e25d052d25264a14c4904aebc383482577bb5d2bb135f3ece88b1b7b0456a6bc` |
| `Battle Racers (Japan).sfc` | 1,048,576 | `64b76ceb` | `ac9233fb2cf241e3c540d29c5d34ae5c4a821b09d86ccf2015a586edc7842096` |
| `Bike Daisuki! Hashiriya Tamashii (Japan).sfc` | 524,288 | `b363fc99` | `3fb25a3b30e897455de88e9e1d5ff2df81e56b89f3fe7b7d9e0248a19a146b4b` |
| `Campus Challenge '92 - Pilotwings (USA).sfc` | 524,288 | `9bfe8684` | `82571a02ac565e079ea269c0d8efc253a1dd68146ee54029f8aeaa751d073772` |
| `Drift King Shutokou Battle '94 - Tsuchiya Keiichi & Bandou Masaaki (Japan).sfc` | 1,572,864 | `33ce298f` | `f6010bbaaad08c3427fa0273461399da15fb56a69be2144beeb688cbcddfe25d` |
| `Drift King Shutokou Battle 2 - Tsuchiya Keiichi & Bandou Masaaki (Japan).sfc` | 1,572,864 | `87aab79a` | `9fdd65a2921d9e2261734d764fcd87987c49b651c06adf60f6e5a9c754c2b7ca` |
| `Dungeon Master (Europe).sfc` | 1,048,576 | `89a67adf` | `e68eaed4eae2b1236264c0307b14bb2872e57471a166294e96ae56b7ba1a5e57` |
| `Dungeon Master (Japan) (Rev 1).sfc` | 1,048,576 | `aa79fa33` | `35ff99319ecc7ce1216c5096f46fcc11659254d570614d683f0f8ef773ed75b8` |
| `Dungeon Master (USA).sfc` | 1,048,576 | `0dfd9ceb` | `2dfc2e037679a62a960dab9682bca6d1b2737f603edd336c8b2fdf05db10cc07` |
| `Final Stretch (Japan).sfc` | 1,572,864 | `8d29f41f` | `4e22d625595dac0cf3c3053d9e715dc227d3bbe24adad826d5b3f2a035553617` |
| `Hanguk Pro Yagu (Korea).sfc` | 1,572,864 | `a21fb1d5` | `ce770d366ef5d956c865b803f98775f19f0c3b1e996f4499ef665bcaf697c47d` |
| `Lock On (USA).sfc` | 524,288 | `84f7e078` | `7e1d6242ae2ec2c23afb876becdcf778098edd4d853234222dc16471cb51df9e` |
| `Michael Andretti's Indy Car Challenge (Japan).sfc` | 1,048,576 | `1128572b` | `126081caccc4bac5d616608c20a3adec9cd50e8f2133824e693921160e835725` |
| `Michael Andretti's Indy Car Challenge (USA).sfc` | 1,048,576 | `0fdb210e` | `d3180e4c20b12e78e7a94a40d1f168d5a8198b21df9586ade0512720b415f67e` |
| `Pilotwings (Europe).sfc` | 524,288 | `def45776` | `f70a72f3d3a65497cdc4d849877a29cf4f7bd10439bb7f5cb8675cdfc0e706d4` |
| `Pilotwings (Japan).sfc` | 524,288 | `77871727` | `d1845de22c3c7f2606bda20e09c8f7a78f92f5cbbb6bfe01f96a1d1e84b30394` |
| `Pilotwings (USA).sfc` | 524,288 | `266c44ed` | `03d0127f5de3237e22ad00de0c20763274da7b71142dde693240ac96d10983a3` |
| `Planet's Champ TG 3000, The (Japan).sfc` | 1,048,576 | `b9b9df06` | `7611e662666a33a9fca7569f26f85faeb687470b0d64ae853de411c0885000f7` |
| `PowerFest 94 - Super Mario Kart (USA).sfc` | 524,288 | `9974b593` | `19eb77affbf8dd068f5d79a3cf80a2084fd73237cd1ae4e47192b4422449e64a` |
| `SD Gundam GX (Japan).sfc` | 1,048,576 | `4dc3d903` | `0cfea1ceee12d8276fedaf08f64e9413dccbd71ab83ae404b10276b893d46f6d` |
| `Soukou Kihei Votoms - The Battling Road (Japan).sfc` | 1,048,576 | `c00f0bc9` | `a0347898ee96b7729ad5781e0784ad2a34469dfdc6755a7c6957501e26398729` |
| `Super 3D Baseball (Japan).sfc` | 1,572,864 | `304123c2` | `0b6835fd11307d5e4adb8a8fc5e84fbbddeef8becddcceab65418da0618cf3f1` |
| `Super Air Diver (Europe).sfc` | 524,288 | `0b57c764` | `dc00b557e85b5f30e2a8cc269e12e55f71802c3024a6f8e9b299f0722a6f4a55` |
| `Super Air Diver (Japan).sfc` | 524,288 | `971e74ba` | `abec092d53fa56dd97b72279fcbe1545762d874daf721c4f3a1f3402da643d9c` |
| `Super Air Diver 2 (Japan) (En).sfc` | 1,310,720 | `a6ad6b0f` | `e0a648561c54c6f44819dfd88d27590a15686a0fc5bb3a67aed94d99323a7c11` |
| `Super Bases Loaded 2 (USA).sfc` | 1,572,864 | `e14128ca` | `ff75fd4b096d48ce4a677c3321266d67077d6c586c9ee6926c7716a34f6d5ce1` |
| `Super F1 Circus Gaiden (Japan).sfc` | 1,310,720 | `6b8ac3b3` | `15a396dcc56cb40dc80733870d2d019cb59b80002ed05e746e4834ac07e22f13` |
| `Super Mario Kart (Europe).sfc` | 524,288 | `56410e5e` | `1bdf422695a30e704e8abb7743b9c178d1ef2b200515a83cd41daef85e6b99e2` |
| `Super Mario Kart (Japan).sfc` | 524,288 | `c8002453` | `c04f517c2675d7a8f3498d958f097443dfaa0e66606c69c59b58a915b3454973` |
| `Super Mario Kart (USA).sfc` | 524,288 | `cd80db86` | `2ada8919688087be60a6a48cace8f877add60c45d2e5d09e2442faa55be62a49` |
| `Suzuka 8 Hours (Japan) (En).sfc` | 1,048,576 | `b846b00d` | `3aef80a3997b500a71ae76ac170c49b04f44dd8d9b60c0141d8aca0bb30567ac` |
| `Suzuka 8 Hours (USA).sfc` | 1,048,576 | `54740b9b` | `ed8fa0dd7bb99957304e2de37f7dd79769d6534f9b01e290332b862f8ab43c4e` |
| `Top Gear 3000 (Europe).sfc` | 1,048,576 | `493fdb13` | `4d7c81b0bad57a4c1c410fae4e58cd95fe25c29d7fb922778530cd457b5502e7` |
| `Top Gear 3000 (USA).sfc` | 1,048,576 | `a20be998` | `6be49983976564f1fd9eff2f14f5bb41d3a0ff48573e39318088ecce286aca62` |

MD5 and SHA-1 for each are in [`cartridges.manifest.json`](../cartridges.manifest.json).
**SHA-256 decides**; the rest are published so a copy can be cross-checked against
a database that keys on one of them, and none of them decides anything alone.

## How to use it

```bash
python3 conformance/cartridges.py
```

With nothing here, every check that needs a cartridge reports as skipped rather
than as passed. Point `SNES_CARTRIDGE_DIR` somewhere else to use a library you
keep outside the repository instead.
