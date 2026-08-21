TheAshenGoldenAge\gfx\map\map_object_data\building_locators.txt
game_object_locator={
	name="buildings"
	render_pass=Map
	clamp_to_water_level=yes
	generated_content=no
	layer="building_layer"
	instances={
		{
			id=1
			position={ 271.799835 0.000000 4462.883301 }
			rotation={ -0.000000 -0.960029 -0.000000 0.279900 }
			scale={ 1.000000 1.000000 1.000000 }
		}
		{
			id=2
			position={ 228.109695 0.000000 4356.450195 }
			rotation={ -0.000000 0.066732 -0.000000 -0.997771 }
			scale={ 1.000000 1.000000 1.000000 }
		}
		{
			id=3
			position={ 294.780823 0.000000 4322.118164 }
			rotation={ -0.000000 -0.342900 -0.000000 0.939372 }
			scale={ 1.000000 1.000000 1.000000 }
		}
	}
}

TheAshenGoldenAge\gfx\map\map_object_data\combat_locators.txt
game_object_locator={
	name="combat"
	render_pass=Map
	clamp_to_water_level=yes
	generated_content=no
	layer="unit_layer"
	instances={
		{
			id=0
			position={ 0.000000 0.000000 509.000000 }
			rotation={ 0.000000 0.000000 0.000000 1.000000 }
			scale={ 1.000000 1.000000 1.000000 }
		}
		{
			id=1
			position={ 274.374359 0.000000 4439.049316 }
			rotation={ -0.000000 -0.986924 -0.000000 0.161187 }
			scale={ 1.000000 1.000000 1.000000 }
		}
		{
			id=2
			position={ 263.953583 0.000000 4371.686035 }
			rotation={ -0.000000 0.111731 -0.000000 -0.993739 }
			scale={ 1.000000 1.000000 1.000000 }
		}
	}
}

TheAshenGoldenAge\gfx\map\map_object_data\player_stack_locators.txt
game_object_locator={
	name="unit_stack_player_owned"
	render_pass=Map
	clamp_to_water_level=yes
	generated_content=no
	layer="unit_layer"
	instances={
		{
			id=0
			position={ 3.000000 0.000000 517.000000 }
			rotation={ 0.000000 0.000000 0.000000 1.000000 }
			scale={ 1.000000 1.000000 1.000000 }
		}
		{
			id=1
			position={ 274.573578 0.000000 4469.125977 }
			rotation={ -0.000000 0.132135 -0.000000 0.991232 }
			scale={ 1.000000 1.000000 1.000000 }
		}
		{
			id=2
			position={ 241.968445 0.000000 4360.395508 }
			rotation={ -0.000000 -0.216440 -0.000000 0.976296 }
			scale={ 1.000000 1.000000 1.000000 }
		}
	}
}

TheAshenGoldenAge\gfx\map\map_object_data\siege_locators.txt
game_object_locator={
	name="siege"
	render_pass=Map
	clamp_to_water_level=no
	generated_content=no
	layer="unit_layer"
	instances={
		{
			id=1
			position={ 280.866028 0.000000 4465.129883 }
			rotation={ -0.000000 -0.633989 -0.000000 0.773342 }
			scale={ 1.000000 1.000000 1.000000 }
		}
		{
			id=2
			position={ 249.878876 0.000000 4353.967773 }
			rotation={ -0.000000 0.805906 -0.000000 -0.592044 }
			scale={ 1.000000 1.000000 1.000000 }
		}
		{
			id=3
			position={ 303.769012 0.000000 4329.537109 }
			rotation={ -0.000000 0.436311 -0.000000 -0.899796 }
			scale={ 1.000000 1.000000 1.000000 }
		}
	}
}

TheAshenGoldenAge\gfx\map\map_object_data\stack_locators.txt
game_object_locator={
	name="unit_stack"
	render_pass=Map
	clamp_to_water_level=yes
	generated_content=no
	layer="unit_layer"
	instances={
		{
			id=0
			position={ 0.000000 0.000000 512.000000 }
			rotation={ 0.000000 0.000000 0.000000 1.000000 }
			scale={ 1.000000 1.000000 1.000000 }
		}
		{
			id=1
			position={ 282.000000 0.000000 4455.000000 }
			rotation={ 0.000000 0.000000 0.000000 1.000000 }
			scale={ 1.000000 1.000000 1.000000 }
		}
		{
			id=2
			position={ 259.000000 0.000000 4384.000000 }
			rotation={ 0.000000 0.000000 0.000000 1.000000 }
			scale={ 1.000000 1.000000 1.000000 }
		}
	}
}

TheAshenGoldenAge\common\landed_titles\TAGA_china.txt
h_taga_hanjin = { 
	color = { 255 127 80 }

	capital = c_taga_jingyi

	e_taga_si = {
		color = { 255 30 0 }

		capital = c_taga_luoyang

		k_taga_henan = {
			color = { 255 30 0 }

			capital = c_taga_luoyang

			d_taga_henan = {
				color = { 255 35 0 }

				capital = c_taga_luoyang

				c_taga_luoyang = {
					color = { 255 35 0 }

					b_taga_luoyang = {
						province = 9780

						color = { 255 35 0 }
					}
				}
			}
		}
	}
}



```
TheAshenGoldenAge
├─ 📁.vscode
├─ 📁examples
│  └─ 📄02_china.txt
├─ 📁MISC
│  └─ 📁oldtitles
│     ├─ 📄TAGAtitle_l_simp_chinese.yml
│     └─ 📄TAGA_china.txt
├─ 📁TheAshenGoldenAge
│  ├─ 📁common
│  │  ├─ 📁bookmarks
│  │  │  ├─ 📁bookmarks
│  │  │  │  └─ 📄00_bookmarks.txt
│  │  │  └─ 📁groups
│  │  │     └─ 📄00_bookmark_groups.txt
│  │  ├─ 📁culture
│  │  │  ├─ 📁cultures
│  │  │  │  └─ 📄TAGA_jindy.txt
│  │  │  └─ 📁pillars
│  │  │     ├─ 📄TAGA_ethos.txt
│  │  │     └─ 📄TAGA_heritage.txt
│  │  ├─ 📁landed_titles
│  │  │  └─ 📄TAGA_china.txt
│  │  └─ 📁province_terrain
│  │     ├─ 📄00_province_terrain.txt
│  │     └─ 📄01_province_properties.txt
│  ├─ 📁gfx
│  │  ├─ 📁interface
│  │  │  └─ 📁icons
│  │  │     └─ 📁culture_pillars
│  │  │        └─ 📄ethos_tagamenfa.dds
│  │  └─ 📁map
│  │     └─ 📁map_object_data
│  │        ├─ 📄building_locators.txt
│  │        ├─ 📄changan_building.txt
│  │        ├─ 📄combat_locators.txt
│  │        ├─ 📄player_stack_locators.txt
│  │        ├─ 📄siege_locators.txt
│  │        └─ 📄stack_locators.txt
│  ├─ 📁history
│  │  └─ 📁provinces
│  │     └─ 📄taga_k_jiangzuo.txt
│  ├─ 📁localization
│  │  └─ 📁simp_chinese
│  │     ├─ 📄TAGAbookmark_l_simp_chinese.yml
│  │     ├─ 📄TAGAculture_l_simp_chinese.yml
│  │     └─ 📄TAGAtitle_l_simp_chinese.yml
│  ├─ 📁map_data
│  │  ├─ 📄definition.csv
│  │  ├─ 📄provinces.png
│  │  ├─ 📄provinces.psd
│  │  ├─ 📄provinces备份.psd
│  │  └─ 📄provinces备份2.psd
│  └─ 📄TheAshenGoldenAge.mod
├─ 📁tools
│  ├─ 📁provincedata
│  │  ├─ 📁__pycache__
│  │  │  └─ 📄config.cpython-313.pyc
│  │  ├─ 📄apply.py
│  │  ├─ 📄config.py
│  │  ├─ 📄iso.py
│  │  └─ 📄main.xlsx
│  ├─ 📁utils
│  │  ├─ 📁__pycache__
│  │  │  ├─ 📄get_color.cpython-313.pyc
│  │  │  ├─ 📄get_title.cpython-313.pyc
│  │  │  ├─ 📄LocatorPositionUpdater.cpython-313.pyc
│  │  │  ├─ 📄match_color.cpython-313.pyc
│  │  │  └─ 📄shortest_point.cpython-313.pyc
│  │  ├─ 📄ColorAllocator.py
│  │  ├─ 📄get_color.py
│  │  ├─ 📄get_title.py
│  │  ├─ 📄LocatorPositionUpdater.py
│  │  ├─ 📄match_color.py
│  │  └─ 📄shortest_point.py
│  ├─ 📁__pycache__
│  │  ├─ 📄loca.cpython-313.pyc
│  │  └─ 📄loc_mapobjects.cpython-313.pyc
│  ├─ 📄check_duplicates.py
│  ├─ 📄loca.py
│  ├─ 📄locabetter.py
│  ├─ 📄loc_mapobjects.py
│  ├─ 📄province_history.py
│  └─ 📄regenerate_localization.py
└─ 📄README.md
```