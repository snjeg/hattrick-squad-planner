# CHPP own-senior-player field verification

Milestone 1.1 uses the `players` XML response version 2.7 requested by current Hattrick Organizer (HO), pinned at commit `31622ccd42e104e21a853122ffd269bd9e98dc88` (2026-06-22). The reference points are `core/net/Connector.java` and `core/file/xml/XMLPlayersParser.java`. The public [Hattrick CHPP players field documentation](https://wiki.hattrick.org/wiki/CHPP_Development/XML/players) was also checked for field semantics, although that page labels its version listing as outdated.

| Requested information | Players XML element | Normalized ownership |
| --- | --- | --- |
| stamina | `StaminaSkill` | `PlayerSnapshot.stamina` |
| form | `PlayerForm` | `PlayerSnapshot.form` |
| experience | `Experience` | `PlayerSnapshot.experience` |
| loyalty | `Loyalty` | `PlayerSnapshot.loyalty` |
| injury/status | `InjuryLevel` | `PlayerSnapshot.injury_level` |
| cards/status | `Cards` | `PlayerSnapshot.cards` |
| specialty | `Specialty` | `Player.specialty` |
| mother club | `MotherClubBonus` | `Player.is_mother_club` |
| nationality | `CountryID` | `Player.nationality_id` |
| wage | `Salary` | `PlayerSnapshot.wage` |
| TSI | `TSI` | `PlayerSnapshot.tsi` |

The parser accepts skill elements either directly below `Player` (the documented v2.7 shape used by HO) or inside `PlayerSkills`, preserving compatibility with the existing mock shape.

`MotherClubBonus` is available in the squad list and is persisted as a stable boolean. The actual mother club's team ID/name is not invented: HO parses it from the separate player-details response, which this milestone does not fetch. Existing nullable `mother_club_id` therefore remains unset.

Time-varying observations stay in append-only snapshots. Identity or stable metadata stays on `Player`. The latest-squad read is ordered chronologically by observation time with deterministic tie-breakers.

The CHPP documentation permits `Cards` and `InjuryLevel` to contain `NOT AVAILABLE` while the team is playing. The parser maps only that documented sentinel to `None`; it does not invent a health or suspension state.
