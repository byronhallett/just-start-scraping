from pathlib import Path


class Settings:
    out_dir = Path('C:/TBE/JSH_Byron/')
    # out_dir = Path('/Users/byron/developer/just-start-scraping/output')



def test():
    try:
        test_dir = Settings.out_dir / 'testfile.txt'
        print("writing test to:", test_dir)
        with test_dir.open('a') as file:
            file.write('Test contents')
    except:
        print('directory not found')
        input('press enter to continue...\n')


if __name__ == '__main__':
    test()
